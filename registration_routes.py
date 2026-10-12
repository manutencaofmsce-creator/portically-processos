"""Authenticated panel routes; all case text escaped and all writes CSRF-protected."""
import hashlib
import hmac
import secrets
import json
from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from process_registry import FIELDS


def install_registration(application,env):
    esc=env['esc'];page=env['page']
    def csrf(request):
        session=request.cookies.get('portically_processos_session','')
        return hmac.new(env['SESSION_SECRET'].encode(),('process-form:'+session).encode(),hashlib.sha256).hexdigest()
    def guard(request,form):
        token=str(form.get('csrf',''))
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            raise ValueError('Origem do formulário inválida.')
        if not secrets.compare_digest(token,csrf(request)):
            raise ValueError('Formulário expirado; recarregue a página.')
    def error(status=503,message='Armazenamento seguro indisponível. Tente novamente.'):
        return HTMLResponse(esc(message),status_code=status)
    def shell(title,content):
        return page('<section class="card">'+env['app_header'](title)+content+'</section>',title)
    def fields(data):
        return ''.join(f'<div><label for="p_{k}">{esc(label)}</label><input id="p_{k}" name="{k}" maxlength="{4000 if k in {"parties","summary"} else 500}" value="{esc(data.get(k,""))}" {"required" if k in {"cnj","title","court","source","captured_at"} else ""}></div>' for k,label in FIELDS.items())

    @application.get('/processos',response_class=HTMLResponse)
    def processos(request:Request):
        if not env['auth'](request): return RedirectResponse('/',303)
        try: records=env['registry']().list()
        except Exception: return error()
        cards=''.join(f'<div class="proc section"><h2>{esc(r["metadata"]["title"])}</h2><p class="cnj">{esc(r["metadata"]["cnj"])}</p><p>{esc(r["metadata"]["court"])} · {esc(r["metadata"].get("unit",""))}</p><p>{len(r["pending"])} campos pendentes de validação humana</p><a class="btn" href="/processos/{r["id"]}">Abrir ficha</a></div>' for r in records)
        return shell('Processos',f'<a class="btn" href="/processos/novo">Cadastrar processo</a><p>{len(records)} fichas persistidas</p>'+ (cards or '<p>Nenhum processo cadastrado.</p>'))
    env['processos']=processos

    # Must precede the parameter route.
    @application.get('/processos/novo',response_class=HTMLResponse)
    def novo(request:Request):
        if not env['auth'](request): return RedirectResponse('/',303)
        data={}
        checks=''.join(f'<label class="checkrow"><input type="checkbox" style="width:auto" name="pending" value="{k}" checked>{esc(label)} precisa de validação humana</label>' for k,label in FIELDS.items())
        return shell('Cadastrar processo',f'<p>Cadastre uma ficha por vez. Indique a fonte consultada e a data da coleta com fuso horário (exemplo: 2099-01-01T10:00:00-03:00). Desmarque um campo somente após conferência humana. A inclusão não consulta automaticamente os tribunais.</p><form method="post" action="/processos/novo"><input type="hidden" name="csrf" value="{csrf(request)}"><div class="form-grid">{fields(data)}</div>{checks}<button>Salvar processo</button></form><p>Código da tela: PP-CAD-01</p>')

    @application.post('/processos/novo')
    async def criar(request:Request):
        if not env['auth'](request): return RedirectResponse('/',303)
        try:
            form=await request.form(max_fields=40,max_files=0);guard(request,form)
            identifier=await run_in_threadpool(lambda:env['registry']().create(dict(form),form.getlist('pending'),env['AUTHORIZED_EMAIL']))
        except ValueError as exc: return error(400,str(exc))
        except Exception: return error()
        return RedirectResponse('/processos/'+identifier,303)

    @application.get('/processos/{identifier}',response_class=HTMLResponse)
    def detalhe(identifier:str,request:Request,tab:str='resumo'):
        if not env['auth'](request): return RedirectResponse('/',303)
        try:
            store=env['registry']();r=store.get(identifier)
            if not r: return error(404,'Processo não encontrado.')
            if r.get('renderer')=='legacy' and tab not in {'validacao','historico'}:
                bundle=env['CaseStore'](env['DATABASE_URL'],env['DATA_ENCRYPTION_KEY']).load()
                token=env['case_context'].set(bundle)
                validation_token=env['legacy_validation_context'].set(r.get('legacy_validation',{}))
                try: return env['legacy_detalhe'](r['metadata']['cnj'],request,tab)
                finally:
                    env['legacy_validation_context'].reset(validation_token)
                    env['case_context'].reset(token)
            nav=env['tabs'](tab,r['id'])
            if tab=='validacao':
                checks=''.join(f'<label class="checkrow"><input style="width:auto" type="checkbox" name="confirmed" value="{k}" {"checked" if k not in r["pending"] else ""}>{esc(label)} conferido</label>' for k,label in FIELDS.items())
                content=f'<p>Confirme apenas campos conferidos na fonte. Campos sem informação permanecem pendentes.</p><form method="post" action="/processos/{r["id"]}/validar"><input type="hidden" name="csrf" value="{csrf(request)}"><input type="hidden" name="revision" value="{r["revision"]}">{checks}<label>Observações</label><textarea name="notes" maxlength="4000">{esc(r.get("validation",{}).get("notes",""))}</textarea><button>Salvar validação</button></form>'
            elif tab=='documentos':
                content=''.join('<div class="box">'+''.join(f'<p>{esc(k)}: {esc(v)}</p>' for k,v in d.items())+'</div>' for d in r.get('documents',[])) or '<p>Nenhum documento vinculado. O cadastro não importa arquivos automaticamente.</p>'
            elif tab=='historico':
                content=''.join(f'<div class="box"><p>{esc(e["at"])} · {esc(e["action"])}</p><p>{esc(e.get("actor",e.get("validation",{}).get("actor","")))}</p></div>' for e in store.history(r['id']))
                content+='<h2>Validação anterior preservada</h2><pre>'+esc(json.dumps(r.get('legacy_validation',{}),ensure_ascii=False,indent=2))+'</pre>'
                content+='<h2>Histórico anterior importado</h2><pre>'+esc(json.dumps(r.get('legacy_history',[]),ensure_ascii=False,indent=2))+'</pre>'
            elif tab=='resumo':
                content='<div class="grid">'+''.join(f'<div class="box"><div class="label">{esc(label)}</div><div class="value">{esc(r["metadata"].get(k,"") or "Não informado")}</div><p>{"Pendente de validação humana" if k in r["pending"] else "Conferência humana registrada"}</p></div>' for k,label in FIELDS.items())+'</div>'
            elif tab in {'prazos','partes','movimentacoes'} and r.get('legacy_record'):
                content=''.join(f'<div class="box"><p>{esc(k)}: {esc(v)}</p></div>' for k,v in r['legacy_record'].items())
            else:
                content='<p>Informação não cadastrada nesta ficha. Consulte a fonte indicada; não há sincronização automática.</p>'
            if tab=='resumo' and r.get('legacy_record'):
                content+='<h2>Ficha anterior preservada</h2>'+''.join(f'<p>{esc(k)}: {esc(v)}</p>' for k,v in r['legacy_record'].items())
            return shell(r['metadata']['title'],nav+content+'<p>Código da tela: PP-FIC-01</p>')
        except ValueError: return error(400,'Identificador inválido.')
        except Exception: return error()

    @application.post('/processos/{identifier}/validar')
    async def validar(identifier:str,request:Request):
        if not env['auth'](request): return RedirectResponse('/',303)
        try:
            form=await request.form(max_fields=30,max_files=0);guard(request,form)
            await run_in_threadpool(lambda:env['registry']().validate(identifier,form.getlist('confirmed'),str(form.get('notes','')),env['AUTHORIZED_EMAIL'],int(form.get('revision','0'))))
        except ValueError as exc: return error(400,str(exc))
        except Exception: return error()
        return RedirectResponse('/processos/'+identifier+'?tab=validacao',303)
