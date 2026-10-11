"""Administrative, opt-in DataJud pilot. No web routes or case bundle mutations."""
import argparse
import hashlib
import hmac
import json
import os
import re
import socket
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

import psycopg
from cryptography.fernet import Fernet

ENDPOINTS = {court: f'https://api-publica.datajud.cnj.jus.br/api_publica_{court}/_search'
             for court in ('tjrn', 'tjce', 'trt7', 'trt21', 'trf1')}
FIELDS = ['id', 'tribunal', 'numeroProcesso', 'grau', 'classe', 'assuntos',
          'orgaoJulgador', 'dataAjuizamento', 'dataHoraUltimaAtualizacao',
          '@timestamp', 'nivelSigilo', 'movimentos']
MAX_BYTES = 4 * 1024 * 1024


class SyncError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(status)


def normalize(value, court):
    if court not in ENDPOINTS or not re.fullmatch(r'[0-9]{20}|[0-9]{7}-[0-9]{2}\.[0-9]{4}\.[0-9]\.[0-9]{2}\.[0-9]{4}', value):
        raise SyncError('invalid_input')
    number = re.sub(r'[^0-9]', '', value)
    if int(number[:7] + number[9:] + number[7:9]) % 97 != 1:
        raise SyncError('invalid_input')
    expected = {'tjrn': '820', 'tjce': '806', 'trt7': '507', 'trt21': '521', 'trf1': '401'}[court]
    if number[13:16] != expected:
        raise SyncError('invalid_input')
    return number


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def transport(url, key, payload):
    request = Request(url, data=json.dumps(payload).encode(), method='POST', headers={
        'Authorization': 'APIKey ' + key, 'Content-Type': 'application/json',
        'Accept': 'application/json'})
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise SyncError('response_too_large')
            return json.loads(raw)
    except HTTPError as exc:
        raise SyncError({401: 'access_denied', 403: 'access_denied', 429: 'rate_limited'}.get(exc.code, 'http_error')) from None
    except (URLError, TimeoutError, socket.timeout):
        raise SyncError('network_error') from None
    except (ValueError, UnicodeError):
        raise SyncError('invalid_response') from None


def query(number, court, key, send=transport):
    if not key or '\n' in key or '\r' in key:
        raise SyncError('configuration_error')
    payload = {'size': 100, 'track_total_hits': True, '_source': FIELDS,
               'query': {'match': {'numeroProcesso': number}}}
    data = send(ENDPOINTS[court], key, payload)
    try:
        hits = data['hits']['hits']
        total = data['hits']['total']
        count = total['value'] if isinstance(total, dict) else total
        if data.get('timed_out') or data.get('_shards', {}).get('failed', 0):
            raise SyncError('partial_response')
        if isinstance(total, dict) and total.get('relation') != 'eq':
            raise SyncError('partial_response')
        if not isinstance(hits, list) or not isinstance(count, int) or count != len(hits):
            raise SyncError('partial_response')
        records = []
        for hit in hits:
            source = hit['_source']
            if source.get('numeroProcesso') != number or source.get('tribunal') != court.upper():
                raise SyncError('identity_mismatch')
            if source.get('nivelSigilo', 0) != 0:
                raise SyncError('restricted_data')
            movements = source.get('movimentos', [])
            if not isinstance(movements, list) or any(not isinstance(m, dict) or not all(k in m for k in ('codigo', 'nome', 'dataHora')) for m in movements):
                raise SyncError('invalid_response')
            record = {k: source[k] for k in FIELDS if k in source and k != 'movimentos'}
            # A fresh snapshot is kept for each attempt; duplicates within a snapshot collapse.
            unique = {json.dumps(m, sort_keys=True, ensure_ascii=False): m for m in movements}
            record['movimentos'] = [unique[k] for k in sorted(unique)]
            records.append(record)
        return records
    except (KeyError, TypeError, AttributeError, ValueError):
        raise SyncError('invalid_response') from None


class SyncStore:
    def __init__(self, database_url, encryption_key, hmac_key):
        if not database_url or len(hmac_key) < 32:
            raise SyncError('configuration_error')
        self.url, self.box, self.key = database_url, Fernet(encryption_key), hmac_key.encode()

    def connect(self):
        return psycopg.connect(self.url, connect_timeout=10)

    def initialize(self):
        with self.connect() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(722301)')
            conn.execute('''CREATE TABLE IF NOT EXISTS judicial_sync_runs_v1(
                id uuid PRIMARY KEY, process_hash text NOT NULL, source text NOT NULL,
                started_at timestamptz NOT NULL, finished_at timestamptz,
                status text NOT NULL, encrypted_payload text)''')

    def fingerprint(self, number, court):
        return hmac.new(self.key, ('datajud-v1:' + court + ':' + number).encode(), hashlib.sha256).hexdigest()

    def run(self, number, court, api_key, send=transport):
        number = normalize(number, court)
        run_id = str(uuid.uuid4())
        fingerprint = self.fingerprint(number, court)
        # Persist before network access; serialize same-process runs across workers.
        with self.connect() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(%s)', (int(fingerprint[:15], 16),))
            last = conn.execute('''SELECT started_at FROM judicial_sync_runs_v1
                WHERE process_hash=%s ORDER BY started_at DESC LIMIT 1''', (fingerprint,)).fetchone()
            now = datetime.now(timezone.utc)
            if last and (now - last[0]).total_seconds() < 60:
                raise SyncError('cooldown')
            conn.execute('''INSERT INTO judicial_sync_runs_v1
                (id,process_hash,source,started_at,status) VALUES (%s,%s,%s,%s,'started')''',
                         (run_id, fingerprint, ENDPOINTS[court], now))
        records = []
        try:
            records = query(number, court, api_key, send)
            status = 'success' if records else 'not_found'
        except SyncError as exc:
            status = exc.status
        except Exception:
            status = 'unexpected_error'
        envelope = {'number': number, 'court': court, 'records': records,
                    'documents': [], 'documents_status': 'not_provided_by_datajud',
                    'human_validation': 'pending'}
        encrypted = self.box.encrypt(json.dumps(envelope, ensure_ascii=False).encode()).decode()
        with self.connect() as conn:
            conn.execute('''UPDATE judicial_sync_runs_v1 SET finished_at=%s,status=%s,
                encrypted_payload=%s WHERE id=%s''', (datetime.now(timezone.utc), status, encrypted, run_id))
        return {'run_id': run_id, 'status': status, 'records': len(records)}

    def history(self, number, court):
        """Operator-only metadata. Does not decrypt case data or print process identifiers."""
        fingerprint = self.fingerprint(normalize(number, court), court)
        with self.connect() as conn:
            return conn.execute('''SELECT id,source,started_at,finished_at,status
                FROM judicial_sync_runs_v1 WHERE process_hash=%s ORDER BY started_at''', (fingerprint,)).fetchall()


def main():
    parser = argparse.ArgumentParser(description='DataJud pilot V1 (operator only)')
    parser.add_argument('--authorized-personal-use', action='store_true')
    parser.add_argument('--history', action='store_true')
    args = parser.parse_args()
    if not args.authorized_personal_use:
        parser.error('Confirm authorized personal, non-commercial use after reviewing CNJ terms.')
    try:
        # No case numbers or keys in command-line arguments, files or public logs.
        number, court = os.environ['DATAJUD_PROCESS_NUMBER'], os.environ['DATAJUD_COURT']
        store = SyncStore(os.environ['DATABASE_URL'], os.environ['DATA_ENCRYPTION_KEY'], os.environ['DATA_HMAC_KEY'])
        normalize(number, court)
        store.initialize()
        if args.history:
            print(json.dumps(store.history(number, court), default=str))
            return 0
        result = store.run(number, court, os.environ.get('DATAJUD_API_KEY', ''))
        print(json.dumps(result))
        return 0 if result['status'] in ('success', 'not_found') else 1
    except Exception:
        print(json.dumps({'status': 'pilot_failed', 'notice': 'Review configuration or protected sync history.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
