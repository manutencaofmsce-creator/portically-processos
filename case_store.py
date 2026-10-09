"""Encrypted case content, scoped to an authenticated request. No public defaults."""
import html
import json
from collections.abc import Mapping
from contextvars import ContextVar
import psycopg
from cryptography.fernet import Fernet

case_context = ContextVar('case_bundle')


def validate_bundle(bundle):
    if not isinstance(bundle, dict) or set(bundle) != {'main', 'related', 'title', 'fragments'}:
        raise ValueError('Invalid case bundle')
    for section, keys in [('main', {'cnj','court','unit','phase','source','sync'}),
                          ('related', {'cnj','court','unit','kind','class','purpose','source','origin','sync'})]:
        if not isinstance(bundle[section],dict) or set(bundle[section]) != keys:
            raise ValueError('Invalid case schema')
        if not all(isinstance(v,str) for v in bundle[section].values()):
            raise ValueError('Invalid field type')
    if not isinstance(bundle['title'],str) or not isinstance(bundle['fragments'],dict):
        raise ValueError('Invalid content')
    if not all(isinstance(k,str) and isinstance(v,str) for k,v in bundle['fragments'].items()):
        raise ValueError('Invalid fragments')
    # Templates are trusted operator-imported presentation content, never user input.
    import ast
    from pathlib import Path
    required={n.args[0].value for n in ast.walk(ast.parse(Path(__file__).with_name('app.py').read_text()))
              if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='case_fragment'}
    if set(bundle['fragments']) != required:
        raise ValueError('Incompatible presentation schema')
    return bundle


class CaseMapping(Mapping):
    def __init__(self, section): self.section=section
    def __getitem__(self,key): return html.escape(case_context.get()[self.section][key],quote=True)
    def __iter__(self): return iter(case_context.get()[self.section])
    def __len__(self): return len(case_context.get()[self.section])


def case_title(): return html.escape(case_context.get()['title'],quote=True)
def case_fragment(key): return case_context.get()['fragments'][key]


class CaseStore:
    def __init__(self, url, key):
        if not url or not key: raise ValueError('Protected storage not configured')
        self.url=url
        self.box=Fernet(key.encode())

    def initialize(self,conn):
        conn.execute('''CREATE TABLE IF NOT EXISTS protected_case_bundles(
            slot TEXT PRIMARY KEY, payload_cipher TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now())''')

    def import_once(self,bundle):
        validate_bundle(bundle)
        encrypted=self.box.encrypt(json.dumps(bundle,ensure_ascii=False).encode()).decode()
        with psycopg.connect(self.url) as conn:
            conn.execute('SELECT pg_advisory_xact_lock(731224010022)')
            self.initialize(conn)
            result=conn.execute('INSERT INTO protected_case_bundles(slot,payload_cipher) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING slot',('primary',encrypted)).fetchone()
            if not result: raise ValueError('Case already exists; import refused')

    def load(self):
        with psycopg.connect(self.url) as conn:
            row=conn.execute('SELECT payload_cipher FROM protected_case_bundles WHERE slot=%s',('primary',)).fetchone()
        if not row: raise ValueError('No imported case')
        return validate_bundle(json.loads(self.box.decrypt(row[0].encode())))
