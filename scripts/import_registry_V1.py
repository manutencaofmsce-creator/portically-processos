"""Authorized, atomic, non-destructive import from V22 and the latest legacy source."""
import ast
import json
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from case_store import CaseStore,validate_bundle
from process_registry import ProcessRegistry,FIELDS
from scripts.import_case_V1 import extract


def import_existing(store,legacy_source,actor):
    tree=ast.parse(legacy_source)
    constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body
               if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
               and n.targets[0].id in {'NEW_CASE','VALIDATION','NEW_CASE_VALIDATION'}}
    imported=0
    with psycopg.connect(store.url) as conn:
        conn.execute('SELECT pg_advisory_xact_lock(731224010023)')
        conn.execute('''CREATE TABLE IF NOT EXISTS protected_case_bundles(
            slot TEXT PRIMARY KEY,payload_cipher TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
        row=conn.execute("SELECT payload_cipher FROM protected_case_bundles WHERE slot='primary'").fetchone()
        bundle=validate_bundle(store.unseal(row[0])) if row else validate_bundle(extract(legacy_source))
        if not row:
            conn.execute('INSERT INTO protected_case_bundles(slot,payload_cipher) VALUES (%s,%s)',('primary',store.seal(bundle)))
        payloads=[]
        for key in ('main','related'):
            old=bundle[key]
            metadata={'cnj':old['cnj'],'title':bundle['title'] if key=='main' else old.get('purpose','Processo relacionado'),
                      'court':old['court'],'unit':old['unit'],'source':old['source'],'class':old.get('class',''),
                      'status':old.get('phase',''),'captured_at':'','summary':'','parties':'','source_url':''}
            payloads.append({'metadata':metadata,'pending':sorted(FIELDS),'documents':[],
                             'validation':constants.get('VALIDATION',{}) if key=='main' else {},
                             'legacy_validation':constants.get('VALIDATION',{}) if key=='main' else {},
                             'renderer':'legacy','legacy_section':key})
        records=[]
        if conn.execute("SELECT to_regclass('public.process_records')").fetchone()[0]:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute('SELECT * FROM process_records');records=cur.fetchall()
        new=constants.get('NEW_CASE')
        if new and not any(r['cnj']==new['cnj'] for r in records):
            records.append(dict(new,unit_name=new['unit'],class_name=new['class'],latest_decision_at=new['decision_at']))
        for old in records:
            metadata={'cnj':old['cnj'],'title':old['title'],'court':old['court'],'unit':old.get('unit_name',''),
                      'class':old.get('class_name',''),'parties':old.get('claimant',''),'source':old['source'],
                      'source_url':old.get('official_url',''),'captured_at':'','status':old.get('operational_status',''),
                      'summary':old.get('official_summary','')}
            documents=[];validation={};history=[]
            with conn.cursor(row_factory=dict_row) as cur:
                for table,target,column in [('process_documents',documents,'process_cnj'),('process_validations',None,'process_cnj'),('audit_log',history,'entity_id')]:
                    if not conn.execute('SELECT to_regclass(%s)',('public.'+table,)).fetchone()[0]:continue
                    cur.execute(f'SELECT * FROM {table} WHERE {column}=%s',(old['cnj'],))
                    rows=cur.fetchall()
                    # datetime/Decimal metadata are retained without lossy printing.
                    rows=json.loads(json.dumps(rows,default=str))
                    if target is not None:target.extend(rows)
                    elif rows:validation=rows[0]
            if not documents and old.get('document_id'):
                documents=[{k:old[k] for k in ('document_id','decision_id','decision_at','judge','source','official_url','document_sha256') if k in old}]
            confirmed=set()
            for key,items in {'metadata_ok':{'cnj','court','unit','class','parties'},'status_ok':{'status'}}.items():
                if validation.get(key):confirmed|=items
            payloads.append({'metadata':metadata,'pending':sorted(set(FIELDS)-confirmed),'documents':documents,
                             'validation':validation or constants.get('NEW_CASE_VALIDATION',{}),
                             'legacy_validation':validation or constants.get('NEW_CASE_VALIDATION',{}),
                             'legacy_record':json.loads(json.dumps(old,default=str)),'legacy_history':history,'renderer':'generic'})
        for payload in payloads:
            exists=conn.execute('SELECT 1 FROM encrypted_process_registry WHERE cnj_hash=%s',(store.fingerprint(payload['metadata']['cnj']),)).fetchone()
            if exists:continue  # Never overwrite a panel edit or duplicate an audit event.
            identifier=store.insert(payload,actor,conn)
            store.event(conn,identifier,{'action':'legacy_import','actor':actor,'validation':payload['validation'],
                                        'history':payload.get('legacy_history',[])})
            imported+=1
    return imported


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('legacy_source',type=Path)
    p.add_argument('--confirm-authorized-import',action='store_true',required=True)
    args=p.parse_args()
    try:
        actor=os.environ['AUTHORIZED_EMAIL']
        store=ProcessRegistry(os.environ['DATABASE_URL'],os.environ['DATA_ENCRYPTION_KEY'],os.environ['DATA_HMAC_KEY'])
        store.initialize()
        count=import_existing(store,args.legacy_source.read_text(),actor)
    except Exception:
        print('Importação recusada ou indisponível; nenhum conteúdo registrado em logs.',file=sys.stderr)
        sys.exit(1)
    print(f'Importação confirmada: {count} fichas novas. Registros existentes preservados.')
