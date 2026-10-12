"""Fictional registration, cryptography and preservation regression suite."""
import ast
import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import pytest
import psycopg
from cryptography.fernet import Fernet,InvalidToken
from fastapi.testclient import TestClient
import app
from process_registry import ProcessRegistry,FIELDS,clean_metadata
from scripts.import_registry_V1 import import_existing
from tests.test_case_privacy_V1 import fictional_bundle


def fake_cnj(seq=9000001):
    # Deliberately synthetic sequence/year; never consult any judicial service.
    base=str(seq)+'2099'+'8'+'99'+'9999'
    return str(seq)+f'{98-int(base+"00")%97:02d}'+base[7:]


def metadata(seq=9000001):
    return dict(cnj=fake_cnj(seq),title='Pessoa Fictícia <script>x</script>',court='Tribunal Fictício',
                unit='Unidade Fictícia',source='Documento fictício',captured_at='2099-01-01T10:00:00-03:00',
                source_url='https://example.test/documento',summary='Resumo fictício')


def test_metadata_rejects_bad_cnj_missing_source_date_and_script_url():
    for change in [{'cnj':'abc'},{'cnj':fake_cnj()[:-1]+'0'},{'source':''},
                   {'captured_at':'2099-01-01'},{'source_url':'javascript:alert(1)'},
                   {'source_url':'https://u:p@example.test/'},{'title':'a'*501}]:
        with pytest.raises(ValueError):clean_metadata(dict(metadata(),**change))
    assert clean_metadata(metadata())['source_url'].startswith('https:')


@pytest.fixture
def registry():
    url=os.environ.get('TEST_DATABASE_URL')
    if not url:pytest.skip('Requires isolated PostgreSQL')
    store=ProcessRegistry(url,Fernet.generate_key().decode(),'fictional-index-secret-at-least-32-bytes')
    with psycopg.connect(url) as conn:
        conn.execute('DROP TABLE IF EXISTS encrypted_process_events,encrypted_process_registry,protected_case_bundles CASCADE')
    store.initialize()
    return store


@pytest.fixture
def web(monkeypatch):
    monkeypatch.setattr(app,'SESSION_SECRET','fictional-session-secret-for-tests-only')
    monkeypatch.setattr(app,'AUTHORIZED_EMAIL','operator@example.test')
    monkeypatch.setattr(app,'init_db',lambda:None)
    monkeypatch.setattr(app,'otp_service',lambda:Mock())
    store=Mock();store.list.return_value=[];store.create.return_value=str(uuid.uuid4())
    monkeypatch.setattr(app,'registry',lambda:store)
    with TestClient(app.app,base_url='https://testserver') as c:yield c,store


def login(client):client.cookies.set('portically_processos_session',app.make_session('operator@example.test'))
def token(client):
    return re.search('name="csrf" value="([^"]+)"',client.get('/processos/novo').text)[1]


@pytest.mark.parametrize('path',['/processos','/processos/novo','/processos/ficticio'])
def test_no_read_without_session(web,path):
    client,store=web;assert client.get(path,follow_redirects=False).status_code==303
    store.list.assert_not_called();store.get.assert_not_called()


def test_csrf_authorization_and_valid_form(web):
    c,s=web
    assert c.post('/processos/novo',data=metadata(),follow_redirects=False).status_code==303
    s.create.assert_not_called();login(c)
    assert c.post('/processos/novo',data=metadata()).status_code==400
    assert c.post('/processos/novo',data=dict(metadata(),csrf=token(c)),headers={'Origin':'https://evil.example.test'}).status_code==400
    s.create.assert_not_called()
    response=c.post('/processos/novo',data=dict(metadata(),csrf=token(c),pending=['cnj','title']),follow_redirects=False)
    assert response.status_code==303;s.create.assert_called_once()


def test_storage_failure_and_escaping(web):
    c,s=web;login(c);s.list.side_effect=RuntimeError('secret database password')
    response=c.get('/processos');assert response.status_code==503
    assert 'secret' not in response.text;assert 'no-store' in response.headers['cache-control']
    s.list.side_effect=None;s.list.return_value=[dict(id=str(uuid.uuid4()),metadata=metadata(),pending=['cnj'])]
    response=c.get('/processos');assert '&lt;script&gt;' in response.text and '<script>x' not in response.text


def test_atomic_registration_duplicate_roundtrip_and_encryption(registry):
    identifier=registry.create(metadata(),set(FIELDS),'operator@example.test')
    assert len(registry.list())==1
    assert registry.get(fake_cnj())['id']==identifier
    with pytest.raises(ValueError):registry.create(metadata(),[],'operator@example.test')
    assert len(registry.history(identifier))==1
    with psycopg.connect(registry.url) as conn:
        raw=conn.execute('SELECT cnj_hash,payload_cipher FROM encrypted_process_registry').fetchone()
        events=conn.execute('SELECT payload_cipher FROM encrypted_process_events').fetchone()[0]
    assert fake_cnj() not in str(raw) and 'Pessoa' not in str(raw) and 'operator@' not in events
    wrong=ProcessRegistry(registry.url,Fernet.generate_key().decode(),'fictional-index-secret-at-least-32-bytes')
    with pytest.raises(InvalidToken):wrong.list()


def test_audit_failure_rolls_back_create_and_validation(registry,monkeypatch):
    i=registry.create(metadata(),set(FIELDS),'operator@example.test')
    monkeypatch.setattr(registry,'event',Mock(side_effect=RuntimeError('simulated audit outage')))
    with pytest.raises(RuntimeError):registry.create(metadata(9000002),[],'operator@example.test')
    with pytest.raises(RuntimeError):registry.validate(i,['title'],'note','operator@example.test',1)
    assert len(registry.list())==1 and registry.get(i)['revision']==1


def test_validation_preserves_documents_and_conflicting_revisions(registry):
    i=registry.create(metadata(),set(FIELDS),'operator@example.test')
    with ThreadPoolExecutor(2) as pool:
        tasks=[pool.submit(registry.validate,i,['title'],'fictitious note','operator@example.test',1) for _ in range(2)]
        results=[]
        for task in tasks:
            try:task.result();results.append('ok')
            except ValueError:results.append('conflict')
    assert sorted(results)==['conflict','ok']
    r=registry.get(i);assert r['revision']==2 and 'title' not in r['pending']
    assert 'parties' in r['pending'] and len(registry.history(i))==2


def test_additive_import_preserves_bundle_record_docs_validation_audit(registry):
    bundle=fictional_bundle()
    # Registry index expects identifiers with digits, use exclusively generated synthetic CNJs.
    bundle['main']['cnj']=fake_cnj(9000003);bundle['related']['cnj']=fake_cnj(9000004)
    source='\n'.join(f'{k.upper()}={repr(bundle[k])}' for k in ('main','related','title'))
    source+='\nVALIDATION={"cnj":True}\ndef validation_html():\n return "<p>Fictício</p>"\ndef tab_content(tab):\n return "<p>Outro fictício</p>"\n'
    new=dict(metadata(9000005),unit_name='Unidade Fictícia',class_name='Fictícia',claimant='Pessoa Fictícia',operational_status='Teste')
    with psycopg.connect(registry.url) as conn:
        # Mirrors minimal legacy tables while retaining all metadata dynamically.
        conn.execute('DROP TABLE IF EXISTS process_records,process_documents,process_validations,audit_log')
        conn.execute('CREATE TABLE process_records(cnj TEXT PRIMARY KEY,title TEXT,court TEXT,source TEXT,unit_name TEXT,class_name TEXT,claimant TEXT,operational_status TEXT)')
        conn.execute('INSERT INTO process_records VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',tuple(new[k] for k in ('cnj','title','court','source','unit_name','class_name','claimant','operational_status')))
        conn.execute('CREATE TABLE process_documents(id TEXT,process_cnj TEXT,sha256 TEXT,official_url TEXT)')
        conn.execute('INSERT INTO process_documents VALUES (%s,%s,%s,%s)',('FAKE-DOC',new['cnj'],'f'*64,'https://example.test/ficticio'))
        conn.execute('CREATE TABLE process_validations(process_cnj TEXT,metadata_ok BOOLEAN,notes TEXT)')
        conn.execute('INSERT INTO process_validations VALUES (%s,true,%s)',(new['cnj'],'Nota fictícia preservada'))
        conn.execute('CREATE TABLE audit_log(entity_id TEXT,action TEXT,details TEXT)')
        conn.execute('INSERT INTO audit_log VALUES (%s,%s,%s)',(new['cnj'],'OLD_EVENT','Histórico fictício'))
        # Already imported V22 bundle, compatible with current fragment schema.
        conn.execute('CREATE TABLE protected_case_bundles(slot TEXT PRIMARY KEY,payload_cipher TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT now())')
        conn.execute('INSERT INTO protected_case_bundles(slot,payload_cipher) VALUES (%s,%s)',('primary',registry.seal(bundle)))
    assert import_existing(registry,source,'operator@example.test')==3
    assert import_existing(registry,source,'operator@example.test')==0
    r=registry.get(new['cnj']);assert r['documents'][0]['id']=='FAKE-DOC'
    assert r['validation']['notes']=='Nota fictícia preservada'
    assert r['legacy_history'][0]['action']=='OLD_EVENT'
    registry.validate(r['id'],['title'],'new note','operator@example.test',1)
    assert registry.get(r['id'])['documents']==r['documents']
    with psycopg.connect(registry.url) as conn:
        assert conn.execute('SELECT notes FROM process_validations').fetchone()[0]=='Nota fictícia preservada'
        assert conn.execute('SELECT count(*) FROM process_documents').fetchone()[0]==1


def test_concurrent_duplicate_insert_keeps_one_record(registry):
    with ThreadPoolExecutor(2) as pool:
        futures=[pool.submit(registry.create,metadata(),set(FIELDS),'operator@example.test') for _ in range(2)]
        success=0
        for task in futures:
            try:task.result();success+=1
            except ValueError:pass
    assert success==1 and len(registry.list())==1


def test_source_only_import_new_case_and_idempotent_restart(registry):
    bundle=fictional_bundle()
    bundle['main']['cnj']=fake_cnj(9000006);bundle['related']['cnj']=fake_cnj(9000007)
    new=dict(cnj=fake_cnj(9000008),title='Ficha Fictícia',court='Tribunal Fictício',unit='Unidade Fictícia',
             **{'class':'Classe Fictícia'},claimant='Pessoa Fictícia',source='Fonte Fictícia',
             decision_at='2099-01-01',document_id='FAKE-SOURCE-DOC',official_url='https://example.test/documento',
             document_sha256='a'*64,decision_id='FAKE-DECISION',judge='Juiz Fictício',next_step='Passo fictício')
    count=len(bundle['fragments'])
    source='\n'.join(f'{k.upper()}={repr(bundle[k])}' for k in ('main','related','title'))
    source+='\nNEW_CASE='+repr(new)+'\nNEW_CASE_VALIDATION={"metadata":False}\nVALIDATION={"cnj":True}'
    source+='\ndef validation_html():\n return '+repr(['<p>Fictício</p>']*count)+'\ndef tab_content(tab):\n return None\n'
    with psycopg.connect(registry.url) as conn:
        conn.execute('DROP TABLE IF EXISTS process_records,process_documents,process_validations,audit_log')
    assert import_existing(registry,source,'operator@example.test')==3
    assert registry.get(new['cnj'])['documents'][0]['document_id']=='FAKE-SOURCE-DOC'
    registry.initialize()
    assert import_existing(registry,source,'operator@example.test')==0
    assert len(registry.list())==3


def test_import_audit_failure_is_atomic(registry,monkeypatch):
    bundle=fictional_bundle();bundle['main']['cnj']=fake_cnj(9000009);bundle['related']['cnj']=fake_cnj(9000010)
    source='\n'.join(f'{k.upper()}={repr(bundle[k])}' for k in ('main','related','title'))
    source+='\ndef validation_html():\n return '+repr(['<p>Fictício</p>']*len(bundle['fragments']))+'\ndef tab_content(tab):\n return None\n'
    monkeypatch.setattr(registry,'event',Mock(side_effect=RuntimeError('simulated failure')))
    with pytest.raises(RuntimeError):import_existing(registry,source,'operator@example.test')
    assert not registry.list()
    with psycopg.connect(registry.url) as conn:
        assert not conn.execute("SELECT to_regclass('public.protected_case_bundles')").fetchone()[0]
