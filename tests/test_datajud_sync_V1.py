import os
import subprocess
import sys
from urllib.error import HTTPError, URLError

import pytest
from cryptography.fernet import Fernet, InvalidToken
import datajud_sync_V1 as sync

# Generated synthetic identifier; never query the official server in tests.
def synthetic():
    base = '9999999' + '2026' + '820' + '9999'
    dd = 98 - int(base + '00') % 97
    return base[:7] + f'{dd:02d}' + base[7:]

NUMBER = synthetic()

def response():
    movement = {'codigo': 1, 'nome': 'Evento fictício', 'dataHora': '2026-01-01T00:00:00Z'}
    return {'timed_out': False, '_shards': {'failed': 0}, 'hits': {
        'total': {'value': 1, 'relation': 'eq'}, 'hits': [{'_source': {
            'id': 'fictional-record', 'numeroProcesso': NUMBER, 'tribunal': 'TJRN',
            'grau': 'G1', 'nivelSigilo': 0, 'movimentos': [movement, movement],
            'partes': ['must never persist']}}]}}


def test_query_contract_and_projection():
    def send(url, key, payload):
        assert url == sync.ENDPOINTS['tjrn'] and key == 'test-key'
        assert payload['query'] == {'match': {'numeroProcesso': NUMBER}}
        assert payload['track_total_hits'] and 'partes' not in payload['_source']
        return response()
    records = sync.query(NUMBER, 'tjrn', 'test-key', send)
    assert len(records[0]['movimentos']) == 1 and 'partes' not in records[0]
    assert 'documents' not in records[0]


@pytest.mark.parametrize('value,court', [('invalid','tjrn'), (NUMBER,'tjce'), (NUMBER,'https://evil.test'), ('０'*20,'tjrn'), ('0'*20,'tjrn')])
def test_invalid_input(value, court):
    with pytest.raises(sync.SyncError):
        sync.normalize(value, court)


def test_formatted_number():
    n = NUMBER
    assert sync.normalize(f'{n[:7]}-{n[7:9]}.{n[9:13]}.{n[13]}.{n[14:16]}.{n[16:]}', 'tjrn') == n


@pytest.mark.parametrize('mutation,status', [
    (lambda d: d.update(timed_out=True), 'partial_response'),
    (lambda d: d['_shards'].update(failed=1), 'partial_response'),
    (lambda d: d['hits']['total'].update(relation='gte'), 'partial_response'),
    (lambda d: d['hits']['total'].update(value=101), 'partial_response'),
    (lambda d: d['hits']['hits'][0]['_source'].update(numeroProcesso='wrong'), 'identity_mismatch'),
    (lambda d: d['hits']['hits'][0]['_source'].update(tribunal='TJCE'), 'identity_mismatch'),
    (lambda d: d['hits']['hits'][0]['_source'].update(nivelSigilo=1), 'restricted_data'),
    (lambda d: d['hits']['hits'][0]['_source'].update(movimentos=[{}]), 'invalid_response'),
])
def test_fail_closed(mutation, status):
    data = response()
    mutation(data)
    with pytest.raises(sync.SyncError, match=status):
        sync.query(NUMBER, 'tjrn', 'test', lambda *a: data)


def test_empty_and_malformed():
    assert sync.query(NUMBER, 'tjrn', 'test', lambda *a: {'hits': {'total': {'value': 0, 'relation': 'eq'}, 'hits': []}}) == []
    with pytest.raises(sync.SyncError, match='invalid_response'):
        sync.query(NUMBER, 'tjrn', 'test', lambda *a: {})


@pytest.mark.parametrize('code,status', [(401,'access_denied'), (403,'access_denied'), (429,'rate_limited'), (500,'http_error'), (302,'http_error')])
def test_http_errors(monkeypatch, code, status):
    class Opener:
        def open(self, *a, **k):
            raise HTTPError('url', code, 'private detail', {}, None)
    monkeypatch.setattr(sync, 'build_opener', lambda *a: Opener())
    with pytest.raises(sync.SyncError, match=status) as error:
        sync.transport(sync.ENDPOINTS['tjrn'], 'test', {})
    assert 'private' not in str(error.value)


def test_no_redirect():
    assert sync.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test') is None


def test_missing_key_never_connects():
    with pytest.raises(sync.SyncError, match='configuration_error'):
        sync.query(NUMBER, 'tjrn', '', lambda *a: pytest.fail('No network'))


def test_cli_requires_operator_confirmation():
    result = subprocess.run([sys.executable, 'datajud_sync_V1.py'], capture_output=True, text=True)
    assert result.returncode != 0 and 'Confirm authorized' in result.stderr


@pytest.fixture
def store():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Isolated PostgreSQL unavailable')
    service = sync.SyncStore(url, Fernet.generate_key(), 'fictional-hmac-key-at-least-32-characters')
    service.initialize()
    with service.connect() as conn:
        conn.execute('TRUNCATE judicial_sync_runs_v1')
    return service


def age(store):
    with store.connect() as conn:
        conn.execute("UPDATE judicial_sync_runs_v1 SET started_at=started_at-interval '61 seconds'")


def test_persistence_cipher_history_and_failure(store):
    first = store.run(NUMBER, 'tjrn', 'test', lambda *a: response())
    assert first['status'] == 'success'
    with store.connect() as conn:
        ciphertext, fingerprint = conn.execute('SELECT encrypted_payload,process_hash FROM judicial_sync_runs_v1').fetchone()
    assert NUMBER not in ciphertext and NUMBER not in fingerprint
    envelope = __import__('json').loads(store.box.decrypt(ciphertext.encode()))
    assert envelope['documents'] == [] and envelope['human_validation'] == 'pending'
    assert envelope['records'][0]['numeroProcesso'] == NUMBER
    with pytest.raises(InvalidToken):
        Fernet(Fernet.generate_key()).decrypt(ciphertext.encode())
    with pytest.raises(sync.SyncError, match='cooldown'):
        store.run(NUMBER, 'tjrn', 'test', lambda *a: pytest.fail('cooldown'))
    age(store)
    def fail(*a):
        raise sync.SyncError('access_denied')
    assert store.run(NUMBER, 'tjrn', 'test', fail)['status'] == 'access_denied'
    assert len(store.history(NUMBER, 'tjrn')) == 2
    restarted = sync.SyncStore(store.url, Fernet.generate_key(), 'fictional-hmac-key-at-least-32-characters')
    assert len(restarted.history(NUMBER, 'tjrn')) == 2
    age(store)
    assert store.run(NUMBER, 'tjrn', 'test', lambda *a: response())['status'] == 'success'
    assert len(store.history(NUMBER, 'tjrn')) == 3


def test_database_failure_prevents_network(monkeypatch):
    service = sync.SyncStore('postgresql://unused', Fernet.generate_key(), 'x'*32)
    monkeypatch.setattr(service, 'connect', lambda: (_ for _ in ()).throw(RuntimeError('offline')))
    with pytest.raises(RuntimeError):
        service.run(NUMBER, 'tjrn', 'test', lambda *a: pytest.fail('No network'))
