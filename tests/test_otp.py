"""Integration tests V1. TEST_DATABASE_URL must point to a disposable database."""

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing
import os
import re
import subprocess
import sys
import uuid

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg import sql
import pytest
from fastapi.testclient import TestClient

from otp_auth import OTPAuth

EMAIL = "authorized@example.test"
KEY = "test-otp-key-with-at-least-32-bytes"
BROWSER = "a" * 43
CLIENT = "192.0.2.1"


@pytest.fixture
def service():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    schema = "otp_test_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    svc = OTPAuth(make_conninfo(url, options=f"-c search_path={schema}"), KEY, EMAIL)
    svc.initialize()
    yield svc
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def issue(service, browser=BROWSER, client=CLIENT):
    sent = []

    def sender(email, code):
        sent.append((email, code))
        return {"id": "test-message"}

    result = service.request(EMAIL, browser, client, sender)
    assert result.status == "sent"
    return result.challenge_id, sent[0][1]


def verify(service, challenge, code, browser=BROWSER, client=CLIENT):
    return service.verify(EMAIL, challenge, code, browser, client)


def wrong(code):
    return "000000" if code != "000000" else "111111"


def age_requests(service):
    with service.connect() as conn:
        conn.execute(
            "UPDATE auth_rate_events SET occurred_at=occurred_at-interval '61 seconds' WHERE scope LIKE 'send-%'"
        )


def test_hash_only_and_single_use(service):
    challenge, code = issue(service)
    with service.connect() as conn:
        row = conn.execute(
            "SELECT code_hash,subject_hash,browser_hash FROM auth_otp_challenges"
        ).fetchone()
        assert row[0] != code and all(len(v) == 64 for v in row)
        assert row[0] == service.digest(
            "otp", challenge, service.digest("subject", EMAIL), code
        )
        audit = str(
            conn.execute(
                "SELECT event,subject_hash,client_hash FROM auth_events"
            ).fetchall()
        )
        assert EMAIL not in audit and CLIENT not in audit and BROWSER not in audit
    assert verify(service, challenge, code).status == "verified"
    assert verify(service, challenge, code).status == "invalid"


def test_expiration(service):
    challenge, code = issue(service)
    with service.connect() as conn:
        conn.execute(
            "UPDATE auth_otp_challenges SET created_at=created_at-interval '11 minutes', expires_at=clock_timestamp()-interval '1 second'"
        )
    assert verify(service, challenge, code).status == "invalid"
    with service.connect() as conn:
        assert (
            conn.execute("SELECT state FROM auth_otp_challenges").fetchone()[0]
            == "expired"
        )


def test_five_attempts(service):
    challenge, code = issue(service)
    for _ in range(5):
        assert verify(service, challenge, wrong(code)).status == "invalid"
    assert verify(service, challenge, code).status == "invalid"
    with service.connect() as conn:
        assert conn.execute(
            "SELECT attempts,state FROM auth_otp_challenges"
        ).fetchone() == (5, "exhausted")


def test_repeated_request_preserves_active_code(service):
    challenge, code = issue(service)
    result = service.request(
        EMAIL, BROWSER, CLIENT, lambda *_: pytest.fail("Should not send")
    )
    assert result.status == "limited" and 1 <= result.retry_after <= 61
    assert verify(service, challenge, code).status == "verified"


def test_new_request_does_not_reset_browser_attempt_budget(service):
    old, code = issue(service)
    for _ in range(5):
        verify(service, old, wrong(code))
    age_requests(service)
    new, new_code = issue(service)
    for _ in range(5):
        verify(service, new, wrong(new_code))
    age_requests(service)
    third, third_code = issue(service)
    assert verify(service, third, third_code).status == "limited"
    # Recovery after a finite window; denied attempts don't prolong it.
    with service.connect() as conn:
        conn.execute(
            "UPDATE auth_rate_events SET occurred_at=occurred_at-interval '16 minutes'"
        )
    assert verify(service, third, third_code).status == "verified"


def test_new_success_invalidates_old_code(service):
    old, old_code = issue(service)
    age_requests(service)
    new, new_code = issue(service)
    assert verify(service, old, old_code).status == "invalid"
    assert verify(service, new, new_code).status == "verified"


@pytest.mark.parametrize("failure", ["raise", "empty", "missing-id"])
def test_delivery_failure_preserves_previous_code(service, failure):
    old, code = issue(service)
    age_requests(service)

    def sender(*_):
        if failure == "raise":
            raise RuntimeError("sensitive provider payload")
        return None if failure == "empty" else {"error": "delivery rejected"}

    assert service.request(EMAIL, BROWSER, CLIENT, sender).status == "delivery_failed"
    assert verify(service, old, code).status == "verified"
    with service.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM auth_otp_challenges WHERE state='failed'"
            ).fetchone()[0]
            == 1
        )


def worker_verify(url, challenge, code, browser=BROWSER, client=CLIENT):
    return (
        OTPAuth(url, KEY, EMAIL).verify(EMAIL, challenge, code, browser, client).status
    )


def test_restart_in_fresh_python_process(service):
    challenge, code = issue(service)
    program = "from otp_auth import OTPAuth; import json,sys; a=json.load(sys.stdin); print(OTPAuth(a[0],a[1],a[2]).verify(*a[2:]).status)"
    import json

    result = subprocess.run(
        [sys.executable, "-c", program],
        input=json.dumps(
            [service.database_url, KEY, EMAIL, challenge, code, BROWSER, CLIENT]
        ),
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "verified"


def test_two_workers_only_one_can_consume(service):
    challenge, code = issue(service)
    with ProcessPoolExecutor(
        2, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        results = list(
            pool.map(
                worker_verify, [service.database_url] * 2, [challenge] * 2, [code] * 2
            )
        )
    assert sorted(results) == ["invalid", "verified"]


def test_concurrent_wrong_attempts_cannot_exceed_five(service):
    challenge, code = issue(service)
    with ThreadPoolExecutor(8) as pool:
        results = list(
            pool.map(lambda _: verify(service, challenge, wrong(code)).status, range(8))
        )
    assert set(results) == {"invalid"}
    with service.connect() as conn:
        assert conn.execute(
            "SELECT attempts,state FROM auth_otp_challenges"
        ).fetchone() == (5, "exhausted")


def test_concurrent_requests_only_one_send(service):
    sent = []

    def sender(email, code):
        sent.append(code)
        return {"id": "message"}

    with ThreadPoolExecutor(6) as pool:
        statuses = list(
            pool.map(
                lambda _: service.request(EMAIL, BROWSER, CLIENT, sender).status,
                range(6),
            )
        )
    assert statuses.count("sent") == 1 and statuses.count("limited") == 5
    assert len(sent) == 1


def test_account_request_limit_and_window_recovery(service):
    for _ in range(5):
        issue(service)
        age_requests(service)
    assert (
        service.request(
            EMAIL, BROWSER, CLIENT, lambda *_: pytest.fail("Should not send")
        ).status
        == "limited"
    )
    with service.connect() as conn:
        conn.execute(
            "UPDATE auth_rate_events SET occurred_at=occurred_at-interval '16 minutes'"
        )
    issue(service)


def test_unauthorized_and_wrong_browser_cannot_consume(service):
    assert (
        service.request(
            "other@example.test",
            BROWSER,
            CLIENT,
            lambda *_: pytest.fail("Should not send"),
        ).status
        == "unauthorized"
    )
    challenge, code = issue(service)
    assert verify(service, challenge, code, "b" * 43).status == "invalid"
    assert (
        service.verify("other@example.test", challenge, code, BROWSER, CLIENT).status
        == "invalid"
    )
    assert verify(service, challenge, code).status == "verified"


def test_other_browser_does_not_invalidate_or_lock_legitimate_code(service):
    old, code = issue(service)
    age_requests(service)
    other, other_code = issue(service, "b" * 43, "192.0.2.2")
    for _ in range(12):
        verify(service, other, wrong(other_code), "b" * 43, "192.0.2.2")
    assert verify(service, old, code).status == "verified"


def test_invalid_challenge_and_malformed_codes(service):
    challenge, code = issue(service)
    assert verify(service, "invalid-uuid", code).status == "invalid"
    assert verify(service, challenge, "abcdef").status == "invalid"
    assert verify(service, challenge, "１２３４５６").status == "invalid"
    assert verify(service, challenge, code).status == "verified"


def test_pending_reservation_survives_crash_but_cannot_authenticate(service):
    class Crash(BaseException):
        pass

    sent = []

    def sender(email, code):
        sent.append(code)
        raise Crash()

    with pytest.raises(Crash):
        service.request(EMAIL, BROWSER, CLIENT, sender)
    with service.connect() as conn:
        challenge = str(
            conn.execute("SELECT id FROM auth_otp_challenges").fetchone()[0]
        )
    assert verify(service, challenge, sent[0]).status == "invalid"
    age_requests(service)
    new, code = issue(service)
    assert verify(service, new, code).status == "verified"


def test_delayed_delivery_cannot_replace_newer_code(service):
    from threading import Event

    entered, release = Event(), Event()

    def sender(*_):
        entered.set()
        assert release.wait(10)
        return {"id": "delayed"}

    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(service.request, EMAIL, BROWSER, CLIENT, sender)
        assert entered.wait(10)
        age_requests(service)
        new, code = issue(service)
        release.set()
        assert pending.result().status == "delivery_failed"
    assert verify(service, new, code).status == "verified"


@pytest.fixture
def web(service, monkeypatch):
    import app

    monkeypatch.setattr(app, "DATABASE_URL", service.database_url)
    monkeypatch.setattr(app, "OTP_HMAC_KEY", KEY)
    monkeypatch.setattr(app, "AUTHORIZED_EMAIL", EMAIL)
    monkeypatch.setattr(app, "SESSION_SECRET", "session-secret-at-least-32-bytes-long")
    monkeypatch.setattr(app, "DATA_HMAC_KEY", "radar-test-key")
    from cryptography.fernet import Fernet

    monkeypatch.setattr(app, "DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(app, "RESEND_API_KEY", "test-no-network")
    sent = []

    def sender(payload):
        sent.append(payload)
        return {"id": "mock-resend-id"}

    monkeypatch.setattr(app.resend.Emails, "send", sender)
    with TestClient(app.app, base_url="https://testserver") as client:
        yield app, client, sent


def request_web(client):
    client.get("/")
    response = client.post("/solicitar-codigo", data={"email": EMAIL})
    assert response.status_code == 200
    return re.search(r'name="challenge" value="([^"]+)"', response.text).group(1)


def test_web_resend_session_and_secure_cookies(web):
    app, client, sent = web
    response = client.get("/")
    cookie = response.headers["set-cookie"].lower()
    assert all(v in cookie for v in ["secure", "httponly", "samesite=strict"])
    challenge = request_web(client)
    code = re.search(r"é: ([0-9]{6})", sent[0]["text"]).group(1)
    response = client.post(
        "/validar-codigo",
        data={"email": EMAIL, "challenge": challenge, "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303 and response.headers["location"] == "/painel"
    cookie = response.headers["set-cookie"].lower()
    assert all(v in cookie for v in ["secure", "httponly", "samesite=strict"])
    assert client.get("/processos").status_code == 200
    assert app.valid_session(app.make_session(EMAIL))
    assert not app.valid_session(app.make_session("other@example.test"))
    response = client.post(
        "/validar-codigo", data={"email": EMAIL, "challenge": challenge, "code": code}
    )
    assert response.status_code == 400 and "set-cookie" not in response.headers


def test_web_resend_failure_does_not_leak_payload(web, monkeypatch, capsys):
    app, client, _ = web
    client.get("/")

    def fail(payload):
        raise RuntimeError(str(payload))

    monkeypatch.setattr(app.resend.Emails, "send", fail)
    response = client.post("/solicitar-codigo", data={"email": EMAIL})
    assert response.status_code == 503
    assert EMAIL not in capsys.readouterr().out and EMAIL not in response.text


def test_web_outage_fails_closed(web, monkeypatch, capsys):
    app, client, _ = web
    client.get("/")

    def fail():
        raise RuntimeError("postgres://private:secret@example.test")

    monkeypatch.setattr(app, "otp_service", fail)
    for path, data in [
        ("/solicitar-codigo", {"email": EMAIL}),
        (
            "/validar-codigo",
            {"email": EMAIL, "code": "123456", "challenge": str(uuid.uuid4())},
        ),
    ]:
        response = client.post(path, data=data)
        assert response.status_code == 503 and "set-cookie" not in response.headers
    assert "private" not in capsys.readouterr().out


def test_web_limits_origin_and_authorization(web):
    _, client, sent = web
    assert client.post("/solicitar-codigo", data={"email": EMAIL}).status_code == 400
    client.get("/")
    assert (
        client.post(
            "/solicitar-codigo",
            data={"email": EMAIL},
            headers={"Origin": "https://other.test"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/solicitar-codigo", data={"email": "other@example.test"}
        ).status_code
        == 200
    )
    assert sent == []
    request_web(client)
    response = client.post("/solicitar-codigo", data={"email": EMAIL})
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


def test_configuration_and_concurrent_startup(service):
    with pytest.raises(ValueError):
        OTPAuth(service.database_url, "", EMAIL)
    with service.connect() as conn:
        conn.execute("DROP TABLE auth_otp_challenges, auth_rate_events, auth_events")
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: service.initialize(), range(4)))


def test_expiration_at_exact_deadline(service, monkeypatch):
    challenge, code = issue(service)
    with service.connect() as conn:
        deadline = conn.execute(
            "SELECT expires_at FROM auth_otp_challenges"
        ).fetchone()[0]
    monkeypatch.setattr(service, "now", lambda _: deadline)
    assert verify(service, challenge, code).status == "invalid"


def test_ip_limits_cannot_be_bypassed_by_changing_browser(service):
    for i in range(30):
        assert (
            service.request(
                "other@example.test", str(i), CLIENT, lambda *_: None
            ).status
            == "unauthorized"
        )
    assert (
        service.request(
            EMAIL, BROWSER, CLIENT, lambda *_: pytest.fail("Should not send")
        ).status
        == "limited"
    )
    challenge, code = issue(service, client="192.0.2.8")
    for i in range(30):
        service.verify(EMAIL, "invalid", "123456", str(i), "192.0.2.9")
    assert verify(service, challenge, code, client="192.0.2.9").status == "limited"
    assert verify(service, challenge, code, client="192.0.2.8").status == "verified"


def test_audit_failure_rolls_back_code_consumption(service, monkeypatch):
    challenge, code = issue(service)
    original = service.event

    def fail(*_):
        raise RuntimeError("Audit storage failed")

    monkeypatch.setattr(service, "event", fail)
    with pytest.raises(RuntimeError):
        verify(service, challenge, code)
    with service.connect() as conn:
        assert conn.execute(
            "SELECT attempts,state FROM auth_otp_challenges"
        ).fetchone() == (0, "active")
    monkeypatch.setattr(service, "event", original)
    assert verify(service, challenge, code).status == "verified"


def test_failed_reservation_does_not_send(service, monkeypatch):
    def fail(*_):
        raise RuntimeError("Audit storage failed")

    monkeypatch.setattr(service, "event", fail)
    with pytest.raises(RuntimeError):
        service.request(
            EMAIL, BROWSER, CLIENT, lambda *_: pytest.fail("Should not send")
        )
    with service.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM auth_otp_challenges").fetchone()[0] == 0
        )
        assert conn.execute("SELECT count(*) FROM auth_rate_events").fetchone()[0] == 0


def test_delivery_after_expiration_is_never_activated(service):
    def sender(*_):
        with service.connect() as conn:
            conn.execute(
                "UPDATE auth_otp_challenges SET created_at=created_at-interval '11 minutes',expires_at=clock_timestamp()-interval '1 second'"
            )
        return {"id": "too-late"}

    assert service.request(EMAIL, BROWSER, CLIENT, sender).status == "delivery_failed"
    with service.connect() as conn:
        assert (
            conn.execute("SELECT state FROM auth_otp_challenges").fetchone()[0]
            == "expired"
        )


def test_restart_keeps_attempts_and_request_limits(service):
    challenge, code = issue(service)
    for _ in range(4):
        verify(service, challenge, wrong(code))
    restarted = OTPAuth(service.database_url, KEY, EMAIL)
    assert (
        restarted.request(
            EMAIL, BROWSER, CLIENT, lambda *_: pytest.fail("Should not send")
        ).status
        == "limited"
    )
    assert verify(restarted, challenge, wrong(code)).status == "invalid"
    assert verify(restarted, challenge, code).status == "invalid"


def test_correct_code_on_fifth_attempt(service):
    challenge, code = issue(service)
    for _ in range(4):
        verify(service, challenge, wrong(code))
    assert verify(service, challenge, code).status == "verified"


def test_web_invalid_code_can_be_retried_without_resend(web):
    _, client, sent = web
    challenge = request_web(client)
    code = re.search(r"é: ([0-9]{6})", sent[0]["text"]).group(1)
    response = client.post(
        "/validar-codigo",
        data={"email": EMAIL, "challenge": challenge, "code": wrong(code)},
    )
    assert response.status_code == 400
    assert f'name="challenge" value="{challenge}"' in response.text
    response = client.post(
        "/validar-codigo",
        data={"email": EMAIL, "challenge": challenge, "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303 and len(sent) == 1


def test_app_concurrent_startup_creates_radar_tables(web, service):
    app, _, _ = web
    with service.connect() as conn:
        conn.execute("DROP TABLE radar_items, audit_log")
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: app.startup(), range(4)))
    with service.connect() as conn:
        assert conn.execute("SELECT count(*) FROM radar_items").fetchone()[0] == 0
