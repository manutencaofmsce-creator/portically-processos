"""Encrypted records and audit, committed atomically; no plaintext case defaults."""
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
from cryptography.fernet import Fernet

FIELDS = {'cnj':'Número CNJ', 'title':'Título', 'court':'Tribunal', 'unit':'Unidade',
          'class':'Classe', 'parties':'Partes', 'source':'Fonte das informações',
          'source_url':'Link da fonte', 'captured_at':'Data da coleta',
          'status':'Situação informada', 'summary':'Resumo / observações'}
REQUIRED = {'cnj','title','court','source','captured_at'}


def normalize_cnj(value):
    value=str(value).strip()
    if not re.fullmatch(r'(?:\d{20}|\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})',value):
        raise ValueError('Informe um número CNJ com 20 dígitos.')
    n=re.sub(r'\D','',value)
    if int(n[7:9]) != 98-int(n[:7]+n[9:]+'00')%97:
        raise ValueError('Dígitos verificadores do CNJ inválidos.')
    return f'{n[:7]}-{n[7:9]}.{n[9:13]}.{n[13]}.{n[14:16]}.{n[16:]}'


def clean_metadata(data):
    result={k:str(data.get(k,'')).strip() for k in FIELDS}
    for k,v in result.items():
        if len(v) > (4000 if k in {'summary','parties'} else 500):
            raise ValueError(f'Campo {FIELDS[k]} excede o limite.')
        if k in REQUIRED and not v:
            raise ValueError(f'Informe {FIELDS[k]}.')
    result['cnj']=normalize_cnj(result['cnj'])
    if result['source_url']:
        url=urlsplit(result['source_url'])
        if url.scheme!='https' or not url.hostname or url.username or url.password:
            raise ValueError('A fonte deve usar um link HTTPS sem credenciais.')
    try:
        parsed=datetime.fromisoformat(result['captured_at'])
        if parsed.tzinfo is None: raise ValueError()
        result['captured_at']=parsed.isoformat()
    except ValueError:
        raise ValueError('Informe data e hora da coleta com fuso horário.') from None
    return result


class ProcessRegistry:
    def __init__(self,url,key,hmac_key):
        if not url or len(hmac_key.encode())<32:
            raise ValueError('Protected registry not configured')
        self.url=url
        self.box=Fernet(key.encode())
        self.key=hmac_key.encode()

    def seal(self,data):
        return self.box.encrypt(json.dumps(data,ensure_ascii=False).encode()).decode()

    def unseal(self,data):
        return json.loads(self.box.decrypt(data.encode()))

    def fingerprint(self,cnj):
        return hmac.new(self.key,('process:'+re.sub(r'\D','',cnj)).encode(),hashlib.sha256).hexdigest()

    def initialize(self):
        with psycopg.connect(self.url,connect_timeout=5) as conn:
            conn.execute('SELECT pg_advisory_xact_lock(731224010023)')
            conn.execute(Path(__file__).with_name('migrations').joinpath('003_process_registry_V1.sql').read_text())

    def create(self,data,pending,actor):
        metadata=clean_metadata(data)
        pending=set(pending)
        if not pending <= set(FIELDS): raise ValueError('Campo de validação inválido.')
        populated={k for k,v in metadata.items() if v}
        # Missing optional fields always remain pending, never silently validated.
        pending |= set(FIELDS)-populated
        payload={'metadata':metadata,'pending':sorted(pending),'documents':[],
                 'validation':{'confirmed':sorted(populated-pending),'actor':actor,
                               'at':datetime.now(timezone.utc).isoformat()},'renderer':'generic'}
        return self.insert(payload,actor)

    def insert(self,payload,actor,conn=None):
        if conn is None:
            with psycopg.connect(self.url,connect_timeout=5) as tx:
                return self.insert(payload,actor,tx)
        identifier=str(uuid.uuid4())
        row=conn.execute('''INSERT INTO encrypted_process_registry(id,cnj_hash,payload_cipher)
            VALUES (%s,%s,%s) ON CONFLICT (cnj_hash) DO NOTHING RETURNING id''',
            (identifier,self.fingerprint(payload['metadata']['cnj']),self.seal(payload))).fetchone()
        if not row: raise ValueError('Processo já cadastrado; ficha existente preservada.')
        self.event(conn,identifier,{'action':'create','actor':actor,'pending':payload['pending']})
        return identifier

    def event(self,conn,identifier,payload):
        conn.execute('INSERT INTO encrypted_process_events(process_id,payload_cipher) VALUES (%s,%s)',
                     (identifier,self.seal(payload)))

    def list(self):
        with psycopg.connect(self.url,connect_timeout=5) as conn:
            rows=conn.execute('SELECT id,payload_cipher,revision FROM encrypted_process_registry ORDER BY created_at,id').fetchall()
        return [dict(self.unseal(cipher),id=str(i),revision=r) for i,cipher,r in rows]

    def get(self,identifier):
        try: uuid.UUID(identifier);where='id';value=identifier
        except ValueError: where='cnj_hash';value=self.fingerprint(normalize_cnj(identifier))
        with psycopg.connect(self.url,connect_timeout=5) as conn:
            row=conn.execute(f'SELECT id,payload_cipher,revision FROM encrypted_process_registry WHERE {where}=%s',(value,)).fetchone()
        if not row: return None
        return dict(self.unseal(row[1]),id=str(row[0]),revision=row[2])

    def validate(self,identifier,confirmed,notes,actor,revision):
        confirmed=set(confirmed)
        if not confirmed<=set(FIELDS) or len(notes)>4000: raise ValueError('Validação inválida.')
        with psycopg.connect(self.url,connect_timeout=5) as conn:
            row=conn.execute('SELECT payload_cipher,revision FROM encrypted_process_registry WHERE id=%s FOR UPDATE',(identifier,)).fetchone()
            if not row: raise ValueError('Processo não encontrado.')
            if row[1]!=revision: raise ValueError('Ficha alterada; recarregue antes de validar.')
            p=self.unseal(row[0]); confirmed={k for k in confirmed if p['metadata'].get(k)}
            p['pending']=sorted(set(FIELDS)-confirmed)
            p['validation']={'confirmed':sorted(confirmed),'notes':notes,'actor':actor,'at':datetime.now(timezone.utc).isoformat()}
            conn.execute('UPDATE encrypted_process_registry SET payload_cipher=%s,revision=revision+1,updated_at=now() WHERE id=%s',(self.seal(p),identifier))
            self.event(conn,identifier,{'action':'validate','validation':p['validation']})

    def history(self,identifier):
        with psycopg.connect(self.url,connect_timeout=5) as conn:
            rows=conn.execute('SELECT payload_cipher,created_at FROM encrypted_process_events WHERE process_id=%s ORDER BY id',(identifier,)).fetchall()
        return [dict(self.unseal(p),at=t.isoformat()) for p,t in rows]
