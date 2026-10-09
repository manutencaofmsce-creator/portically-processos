import ast
import json
import os
import re
import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
from cryptography.fernet import Fernet, InvalidToken
from fastapi.testclient import TestClient
import app
from case_store import CaseStore, case_context, validate_bundle
from scripts.import_case_V1 import extract

ROOT=Path(__file__).resolve().parents[1]


def fictional_bundle():
    tree=ast.parse((ROOT/'app.py').read_text())
    keys={n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='case_fragment'}
    # Explicitly non-CNJ test identifiers, reserved domain, invented parties.
    return {'main':dict(cnj='TEST-MAIN',court='Tribunal Fictício',unit='Unidade Fictícia',phase='Teste',source='Fonte Fictícia',sync='Teste'),
            'related':dict(cnj='TEST-RELATED',court='Tribunal Fictício',unit='Unidade Fictícia',kind='Teste',**{'class':'Teste'},purpose='Teste',source='Fonte Fictícia',origin='TEST-MAIN',sync='Teste'),
            'title':'Pessoa Fictícia A x Empresa Fictícia B',
            'fragments':{k:'<p>Conteúdo fictício</p>' for k in keys}}


def test_public_tree_contains_no_cnj_numbers_or_private_payloads():
    files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    cnj=re.compile(rb'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}')
    for name in files:
        path=ROOT/name
        if not path.is_file(): continue
        assert path.suffix not in {'.pyc','.zip'}, name
        assert not cnj.search(path.read_bytes()),name
        assert not name.endswith('.case.json'),name
    tree=ast.parse((ROOT/'app.py').read_text())
    for n in ast.walk(tree):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'MAIN','RELATED','TITLE'} for t in n.targets):
            assert not isinstance(n.value,(ast.Dict,ast.Constant))


def test_fictional_payload_schema_and_escaping():
    bundle=fictional_bundle();validate_bundle(bundle)
    bundle['title']='<script>alert(1)</script>'
    bundle['main']['court']='<img src=x onerror=alert(1)>'
    token=case_context.set(bundle)
    try:
        assert '<script>' not in app.case_title()
        assert '<img' not in app.MAIN['court']
    finally: case_context.reset(token)
    with pytest.raises(LookupError): _=app.MAIN['cnj']


@pytest.fixture
def web(monkeypatch):
    monkeypatch.setattr(app,'init_db',lambda:None)
    monkeypatch.setattr(app,'AUTHORIZED_EMAIL','operator@example.test')
    monkeypatch.setattr(app,'SESSION_SECRET','fictional-session-secret-for-tests-only')
    monkeypatch.setattr(app,'database_status',lambda:(False,'not-linked'))
    with TestClient(app.app,base_url='https://testserver') as client: yield client


@pytest.mark.parametrize('path',['/painel','/processos','/processos/TEST-MAIN','/movimentacoes'])
def test_unauthenticated_never_loads_case(web,path):
    with patch.object(CaseStore,'load',side_effect=AssertionError('No read before auth')):
        response=web.get(path,follow_redirects=False)
    assert response.status_code==303
    assert 'Fictícia' not in response.text


def authorize(web):
    web.cookies.set('portically_processos_session',app.make_session('operator@example.test'))


def test_tabs_work_with_only_fictional_protected_data(web):
    authorize(web)
    with patch.object(app,'CaseStore') as store:
        store.return_value.load.return_value=fictional_bundle()
        for path in ['/painel','/processos','/movimentacoes']:
            assert web.get(path).status_code==200
        for tab in ['resumo','movimentacoes','documentos','relacionados','prazos','partes','validacao','historico']:
            response=web.get('/processos/TEST-MAIN',params={'tab':tab})
            assert response.status_code==200
            assert 'Pessoa Fictícia A' in response.text
            assert response.headers['cache-control']=='no-store, max-age=0'
        assert web.get('/processos/TEST-RELATED').status_code==200
    with pytest.raises(LookupError):case_context.get()


def test_storage_failure_does_not_leak_details(web):
    authorize(web)
    with patch.object(app,'CaseStore',side_effect=RuntimeError('private payload password')):
        response=web.get('/processos')
    assert response.status_code==503
    assert 'private payload' not in response.text
    assert response.headers['cache-control']=='no-store, max-age=0'
    web.cookies.clear()
    assert web.get('/').status_code==200


def test_missing_fragment_refused():
    b=fictional_bundle();b['fragments']={}
    with pytest.raises(ValueError):validate_bundle(b)


def test_legacy_extraction_is_static_and_fictional():
    source='''MAIN={"cnj":"TEST-MAIN"}
RELATED={"cnj":"TEST-RELATED"}
TITLE="Pessoa Fictícia"
raise RuntimeError("must never execute")
def validation_html():
    return f"<p>Fictício {MAIN['cnj']}</p>"
def tab_content(tab):
    return "<p>Outro texto fictício</p>"
'''
    result=extract(source)
    assert result['title']=='Pessoa Fictícia'
    assert list(result['fragments'].values())==['<p>Fictício ','</p>','<p>Outro texto fictício</p>']


def test_encryption_and_wrong_key():
    key=Fernet.generate_key();store=CaseStore('postgresql://example.test/test',key.decode())
    raw=json.dumps(fictional_bundle()).encode()
    cipher=store.box.encrypt(raw)
    assert b'Pessoa' not in cipher and store.box.decrypt(cipher)==raw
    with pytest.raises(InvalidToken):Fernet(Fernet.generate_key()).decrypt(cipher)


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'),reason='Requires isolated PostgreSQL')
def test_postgres_import_roundtrip_duplicate_and_tamper():
    import psycopg
    url=os.environ['TEST_DATABASE_URL'];key=Fernet.generate_key().decode()
    store=CaseStore(url,key);bundle=fictional_bundle()
    with psycopg.connect(url) as conn:conn.execute('DROP TABLE IF EXISTS protected_case_bundles')
    store.import_once(bundle)
    assert store.load()==bundle
    with pytest.raises(ValueError):store.import_once(bundle)
    assert store.load()==bundle
    with psycopg.connect(url) as conn:
        cipher=conn.execute('SELECT payload_cipher FROM protected_case_bundles').fetchone()[0]
        assert bundle['title'] not in cipher
        conn.execute("UPDATE protected_case_bundles SET payload_cipher='invalid'")
    with pytest.raises(InvalidToken):store.load()


def test_case_presentations_cannot_reintroduce_inline_content():
    tree=ast.parse((ROOT/'app.py').read_text())
    for function in tree.body:
        if isinstance(function,ast.FunctionDef) and function.name in {'validation_html','tab_content'}:
            for node in ast.walk(function):
                if isinstance(node,ast.JoinedStr):
                    assert not any(isinstance(v,ast.Constant) and isinstance(v.value,str) and v.value for v in node.values)
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    assert '<' not in node.value
