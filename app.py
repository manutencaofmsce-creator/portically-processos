import os, time, secrets, hashlib, hmac, html
from datetime import datetime, timezone, timedelta
import resend
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

APP_VERSION="1.1.3"
UPDATE_LABEL="Atualização 09 · V9"
AUTHORIZED_EMAIL=os.environ.get("AUTHORIZED_EMAIL","").strip().lower()
SESSION_SECRET=os.environ.get("SESSION_SECRET","")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","").strip()
RESEND_FROM_EMAIL=os.environ.get("RESEND_FROM_EMAIL","acesso@processos.portically.com.br").strip()
resend.api_key=RESEND_API_KEY
OTP_TTL=600
SESSION_TTL=28800
OTP_STORE={}
VALIDATION={"cnj":False,"tribunal":False,"partes":False,"vinculo":False,"documento":False,"prazo":False,"data_ciencia":"","observacoes":"","validated_at":"","validated_by":""}

app=FastAPI(title="Portically Processos",docs_url=None,redoc_url=None)

MAIN={
 "cnj":"0000678-55.2024.5.07.0001","court":"TRT-7","unit":"1ª Vara do Trabalho de Fortaleza/CE",
 "phase":"Execução","source":"PJe / TRT-7","sync":"Aguardando validação humana"
}
RELATED={
 "cnj":"0000869-21.2026.5.21.0008","court":"TRT-21","unit":"8ª Vara do Trabalho de Natal/RN",
 "kind":"Carta Precatória","class":"CartPrecCiv","purpose":"Citação","source":"PJe / TRT-21",
 "origin":"0000678-55.2024.5.07.0001","sync":"Aguardando validação humana"
}
TITLE="Francisco Fábio Dias da Silva x Portically Tecnologia Ltda. e outros"

def esc(v): return html.escape(str(v))

def page(body,title="Portically Processos"):
    return HTMLResponse(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<style>
:root{{--bg:#07111f;--p:#0d1b2e;--p2:#0a1626;--line:#223955;--txt:#e8eef7;--muted:#9fb1c4}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font-family:Arial,sans-serif}}main{{padding:24px 24px 90px}}.wrap{{max-width:1180px;margin:auto}}
.card{{background:linear-gradient(180deg,#0d1b2e 0%,#0a1727 100%);border:1px solid #1f3a55;border-radius:20px;padding:28px;box-shadow:0 24px 70px #0007}}h1{{font-size:32px;margin:.35rem 0 .45rem;letter-spacing:-.02em}}h2{{font-size:19px;margin:0 0 14px}}h3{{font-size:16px;margin:0 0 8px}}p{{color:var(--muted);line-height:1.5}}
.brand{{font-size:12px;letter-spacing:.16em;color:#72bfff;font-weight:700}}.top{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap}}.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}}.header-meta{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}.version-inline{{font-size:12px;color:#9db0c3;background:#081522;border:1px solid #28445f;border-radius:999px;padding:7px 10px;white-space:nowrap}}
.chip{{display:inline-block;padding:6px 9px;border:1px solid #31516f;border-radius:999px;font-size:12px;color:#c9dbec;background:#0b1a2b}}.green{{border-color:#2e6942;color:#9cf0b8}}.amber{{border-color:#705d2a;color:#ffd77b}}
.tabs{{display:flex;gap:8px;overflow:auto;margin:18px 0}}.tab{{white-space:nowrap;padding:10px 12px;border-radius:9px;background:#0a1626;border:1px solid #223955;color:#c4d4e3;text-decoration:none;font-size:13px}}.tab.active{{background:#173c63;color:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.box{{padding:16px;border-radius:14px;background:#091726;border:1px solid #1e3852}}.proc{{padding:20px;border-radius:16px;background:linear-gradient(180deg,#0a192a,#081522);border:1px solid #254561;box-shadow:inset 0 1px 0 #ffffff08}}.section{{margin-top:20px}}.case-title{{max-width:850px}}.case-sub{{margin:.2rem 0 0}}.case-footer{{display:flex;justify-content:space-between;gap:16px;align-items:end;flex-wrap:wrap;margin-top:16px;padding-top:16px;border-top:1px solid #183149}}.case-location{{margin:0;color:#86a7c5}}
.label{{font-size:12px;color:#8fa5ba;text-transform:uppercase}}.value{{margin-top:6px;font-weight:700}}.cnj{{font-family:monospace;font-weight:700;word-break:break-word}}
.notice{{padding:13px;border-radius:12px;background:#0b2136;border:1px solid #295374;color:#c4d9ec;margin-bottom:14px}}.timeline{{border-left:2px solid #2f5271;margin-left:8px;padding-left:20px}}.event{{margin:0 0 18px}}
.link{{margin-left:8px;padding:12px 0 0 22px;border-left:2px solid #345c80;color:#a8bbce}}.deadline{{border-left:4px solid #ffc857}}.validate-card{{padding:18px;border:1px solid #2b4e6c;border-radius:15px;background:#091827;margin-bottom:12px}}.step{{display:grid;grid-template-columns:42px 1fr auto;gap:14px;align-items:start}}.stepn{{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#173c63;border:1px solid #2f6b9f;font-weight:700}}.checkrow{{display:flex;align-items:center;gap:8px;color:#dce9f5;font-weight:700;white-space:nowrap}}.checkrow input{{width:18px;height:18px;margin:0}}.help{{font-size:13px;color:#8fa7bc;margin-top:6px}}.progress{{height:9px;background:#07111f;border:1px solid #203a54;border-radius:999px;overflow:hidden;margin:10px 0}}.progress i{{display:block;height:100%;background:#2f9b5f}}.status-ok{{color:#9cf0b8}}.status-part{{color:#ffd77b}}.status-pend{{color:#9fb1c4}}textarea{{width:100%;min-height:88px;padding:12px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-family:Arial,sans-serif}}
button,.btn{{display:inline-block;padding:12px 15px;border:0;border-radius:10px;background:#1f8cff;color:#fff;font-weight:700;text-decoration:none;cursor:pointer}}input{{width:100%;padding:14px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-size:16px}}label{{display:block;margin:18px 0 8px}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}}.actions form{{margin:0}}.actions form button{{background:#213247}}a{{color:#7fc5ff}}
.badge{{position:fixed;right:14px;bottom:14px;z-index:50;background:#0b1c2d;border:1px solid #315776;border-radius:11px;padding:8px 11px;box-shadow:0 10px 30px #0008;display:flex;align-items:center;gap:7px}}.badge b{{font-size:11px}}.badge span{{font-size:10px;color:#8ec8ff}}.badge small{{display:none}}
@media(max-width:600px){{main{{padding:12px 12px 92px}}.card{{padding:16px}}h1{{font-size:24px}}}}
</style></head><body>
<div class="badge"><b>v{APP_VERSION}</b><span>{UPDATE_LABEL}</span></div>
<main><div class="wrap">{body}</div></main></body></html>""")

def hash_code(email,code):
    return hmac.new(SESSION_SECRET.encode(),f"{email}:{code}".encode(),hashlib.sha256).hexdigest()

def make_session(email):
    exp=int(time.time())+SESSION_TTL
    raw=f"{email}|{exp}"
    sig=hmac.new(SESSION_SECRET.encode(),raw.encode(),hashlib.sha256).hexdigest()
    return f"{raw}|{sig}"

def valid_session(token):
    try:
        email,exp,sig=token.split("|",2)
        raw=f"{email}|{exp}"
        ok=hmac.compare_digest(sig,hmac.new(SESSION_SECRET.encode(),raw.encode(),hashlib.sha256).hexdigest())
        return ok and int(exp)>=int(time.time()) and email==AUTHORIZED_EMAIL
    except Exception:
        return False

def send_otp(email,code):
    if not RESEND_API_KEY: raise RuntimeError("RESEND_API_KEY não configurada")
    return resend.Emails.send({"from":f"Portically Processos <{RESEND_FROM_EMAIL}>","to":[email],
      "subject":"Código de acesso — Portically Processos",
      "text":f"Seu código de acesso ao Portically Processos é: {code}\n\nEle expira em 10 minutos e só pode ser usado uma vez."})

def auth(request): return valid_session(request.cookies.get("portically_processos_session",""))

def tabs(active):
    items=[("resumo","Resumo"),("movimentacoes","Movimentações"),("documentos","Documentos"),
           ("relacionados","Processos relacionados"),("prazos","Prazos"),("partes","Partes"),("validacao","Validação"),("historico","Histórico")]
    return '<div class="tabs">'+''.join(
      f'<a class="tab {"active" if k==active else ""}" href="/processos/{MAIN["cnj"]}?tab={k}">{label}</a>'
      for k,label in items)+'</div>'

def validation_status():
    done=sum(1 for k in ("cnj","tribunal","partes","vinculo","documento","prazo") if VALIDATION.get(k))
    if done==6: return "Validado manualmente",done,"status-ok"
    if done>0: return "Parcialmente validado",done,"status-part"
    return "Aguardando validação humana",done,"status-pend"

def validation_html():
    status,done,css=validation_status()
    pct=int(done/6*100)
    checked=lambda k: "checked" if VALIDATION.get(k) else ""
    return f"""<div class="notice"><b>Como validar:</b> confira cada item diretamente na fonte oficial. Marque somente o que você confirmou. Você pode salvar parcialmente e continuar depois.</div>
<div class="proc"><div class="top"><div><h2>Validação manual do caso</h2><p class="{css}"><b>{status}</b> · {done} de 6 itens confirmados</p></div><div class="version-inline">{pct}% concluído</div></div>
<div class="progress"><i style="width:{pct}%"></i></div>
<form method="post" action="/processos/{MAIN["cnj"]}/validar">
<div class="validate-card"><div class="step"><div class="stepn">1</div><div><h3>Número CNJ</h3><div class="cnj">{MAIN["cnj"]}</div><div class="help">Confira se o número aparece exatamente igual na fonte oficial do TRT-7. Não aceite correspondência aproximada.</div></div><label class="checkrow"><input type="checkbox" name="cnj" {checked("cnj")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">2</div><div><h3>Tribunal e Vara</h3><p><b>{MAIN["court"]}</b> · {MAIN["unit"]}</p><div class="help">Confirme tribunal, cidade e unidade judiciária no cadastro oficial do processo.</div></div><label class="checkrow"><input type="checkbox" name="tribunal" {checked("tribunal")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">3</div><div><h3>Partes</h3><p>Francisco Fábio Dias da Silva × Portically Tecnologia Ltda. e outros</p><div class="help">Confira nomes e posição processual das partes na fonte oficial.</div></div><label class="checkrow"><input type="checkbox" name="partes" {checked("partes")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">4</div><div><h3>Processo relacionado</h3><div class="cnj">{RELATED["cnj"]}</div><p>{RELATED["court"]} · {RELATED["unit"]}</p><div class="help">Confirme que esta carta precatória está vinculada ao processo principal acima e que a finalidade é citação.</div></div><label class="checkrow"><input type="checkbox" name="vinculo" {checked("vinculo")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">5</div><div><h3>Documento</h3><p>Mandado de Citação PJe-JT</p><div class="help">Compare o mandado com o documento oficial: número do processo, destinatário, data, ID/chave de acesso e conteúdo essencial.</div></div><label class="checkrow"><input type="checkbox" name="documento" {checked("documento")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">6</div><div><h3>Prazo e ciência</h3><p>Prazo mencionado no mandado: <b>48 horas</b></p><label>Data da ciência/citação efetiva</label><input type="date" name="data_ciencia" value="{esc(VALIDATION.get("data_ciencia",""))}"><div class="help">Só marque como confirmado depois de verificar a data efetiva de ciência/citação. O sistema não calcula o vencimento automaticamente nesta etapa.</div></div><label class="checkrow"><input type="checkbox" name="prazo" {checked("prazo")}> Confirmado</label></div></div>
<label>Observações da validação</label><textarea name="observacoes" placeholder="Ex.: conferido no PJe do TRT-7; carta precatória confirmada no TRT-21.">{esc(VALIDATION.get("observacoes",""))}</textarea>
<div class="actions"><button type="submit">Salvar validação</button></div>
</form>
</div>
<div class="section"><h2>Registro da validação</h2>
<div class="grid"><div class="box"><div class="label">Status</div><div class="value {css}">{status}</div></div><div class="box"><div class="label">Última validação</div><div class="value">{esc(VALIDATION.get("validated_at") or "Ainda não realizada")}</div></div><div class="box"><div class="label">Usuário</div><div class="value">{esc(VALIDATION.get("validated_by") or "—")}</div></div></div></div>"""

def tab_content(tab):
    if tab=="validacao":
        return validation_html()
    if tab=="movimentacoes":
        return f"""<div class="notice">Eventos abaixo foram extraídos dos documentos enviados. A cronologia oficial completa ainda depende de sincronização.</div>
<div class="timeline">
<div class="event"><h3>Processo principal em execução</h3><p><b>{MAIN["court"]} · {MAIN["cnj"]}</b></p><p>O mandado vinculado informa débito remanescente e referência ao processo principal em Fortaleza/CE.</p><span class="chip amber">Extraído do documento enviado</span></div>
<div class="event"><h3>Carta Precatória no TRT-21</h3><p><b>{RELATED["cnj"]}</b></p><p>Carta destinada ao cumprimento de citação em Natal/RN.</p><span class="chip amber">Extraído do mandado enviado</span></div>
<div class="event"><h3>Mandado de citação identificado</h3><p>Há referência a prazo de 48 horas. O vencimento não será calculado sem validação da ciência/citação.</p><span class="chip amber">Aguardando validação oficial</span></div>
</div>"""
    if tab=="documentos":
        return f"""<div class="notice">O sistema deverá guardar ID oficial, fonte, data de captura, PDF e hash de cada peça. O mandado já está catalogado; PDF oficial e hash permanecem pendentes.</div>
<div class="proc"><span class="chip">MANDADO</span><h3 style="margin-top:10px">Mandado de Citação PJe-JT</h3><p>Processo: <span class="cnj">{RELATED["cnj"]}</span> · TRT-21</p>
<div class="grid"><div class="box"><div class="label">Status</div><div class="value">Identificado nos documentos enviados</div></div><div class="box"><div class="label">Integridade</div><div class="value">PDF oficial + hash pendentes</div></div><div class="box"><div class="label">Fonte</div><div class="value">PJe / TRT-21</div></div></div></div>"""
    if tab=="relacionados":
        return f"""<div class="proc"><span class="chip green">PROCESSO PRINCIPAL</span><h3 style="margin-top:10px">{MAIN["cnj"]}</h3><p>{MAIN["court"]} · {MAIN["unit"]}</p></div>
<div class="link">Vínculo: processo de origem → carta precatória</div>
<div class="proc"><span class="chip">CARTA PRECATÓRIA</span><h3 style="margin-top:10px">{RELATED["cnj"]}</h3><p>{RELATED["court"]} · {RELATED["unit"]}</p>
<div class="grid"><div class="box"><div class="label">Finalidade</div><div class="value">{RELATED["purpose"]}</div></div><div class="box"><div class="label">Classe</div><div class="value">{RELATED["class"]}</div></div><div class="box"><div class="label">Origem</div><div class="value cnj">{RELATED["origin"]}</div></div></div></div>"""
    if tab=="prazos":
        return """<div class="notice">O vencimento definitivo só será calculado após validação da data efetiva de ciência/citação e da regra de contagem.</div>
<div class="box deadline"><div class="label">Mandado de Citação PJe-JT</div><div class="value">48 horas</div><p>Comprovar o pagamento do débito remanescente e, querendo, apresentar a medida processual indicada no mandado.</p><span class="chip amber">Início e vencimento ainda não validados</span></div>"""
    if tab=="partes":
        return """<div class="grid"><div class="box"><div class="label">Autor / Exequente</div><div class="value">Francisco Fábio Dias da Silva</div></div><div class="box"><div class="label">Réu / Executado</div><div class="value">Portically Tecnologia Ltda. e outros</div></div><div class="box"><div class="label">Destinatária indicada no mandado</div><div class="value">Fernanda Geroncio Pinheiro Dantas</div></div></div>"""
    if tab=="historico":
        return f"""<div class="grid"><div class="box"><span class="chip green">ATUAL</span><div class="label" style="margin-top:8px">Versão</div><div class="value">v{APP_VERSION} · {UPDATE_LABEL}</div><p>Abas funcionais, documentos, movimentações, histórico e identificação visual permanente da versão atual.</p></div>
<div class="box"><div class="label">Versão anterior</div><div class="value">v1.1.2 · Atualização 08 · V8</div><p>Agrupamento do caso e vínculo entre processo principal e carta precatória.</p></div></div>"""
    return f"""<div class="notice"><b>Leitura rápida:</b> Processo em fase de execução. Há uma carta precatória vinculada no TRT-21, em Natal/RN, destinada ao cumprimento de citação originada no processo principal de Fortaleza/CE.</div>
<div class="grid"><div class="box"><div class="label">Processo principal</div><div class="value cnj">{MAIN["cnj"]}</div></div><div class="box"><div class="label">Tribunal</div><div class="value">{MAIN["court"]}</div><p>{MAIN["unit"]}</p></div><div class="box"><div class="label">Fase</div><div class="value">{MAIN["phase"]}</div></div><div class="box"><div class="label">Sincronização</div><div class="value">{validation_status()[0]}</div><p>{validation_status()[1]} de 6 itens confirmados</p><a class="btn" href="/processos/{MAIN["cnj"]}?tab=validacao">Iniciar validação</a></div></div>
<div class="section"><h2>Entenda este processo</h2><div class="grid"><div class="box"><h3>Execução</h3><p>Fase em que o Judiciário busca o cumprimento da obrigação ou pagamento indicado no processo.</p></div><div class="box"><h3>Por que há um processo em Natal?</h3><p>O processo principal tramita em Fortaleza/CE. A carta precatória foi aberta no TRT-21 para cumprir uma diligência em Natal/RN.</p></div><div class="box"><h3>Carta Precatória</h3><p>É o instrumento usado para pedir a outro juízo que cumpra uma diligência fora da área do processo principal.</p></div></div></div>"""

@app.get("/health")
def health():
    return {"status":"ok","service":"portically-processos","version":APP_VERSION,"update":UPDATE_LABEL}

@app.get("/",response_class=HTMLResponse)
def login(request:Request):
    if auth(request): return RedirectResponse("/processos",303)
    return page(f"""<section class="card"><div class="brand">PORTICALLY HUB · MÓDULO PROCESSOS</div><h1>Acesso protegido</h1><div class="chips"><span class="chip green">v{APP_VERSION}</span><span class="chip">{UPDATE_LABEL}</span></div><p>Informe o e-mail autorizado. Um código temporário será enviado antes de liberar os dados processuais.</p><form method="post" action="/solicitar-codigo"><label>E-mail</label><input name="email" type="email" required autocomplete="email"><button>Enviar código de acesso</button></form></section>""")

@app.post("/solicitar-codigo",response_class=HTMLResponse)
def solicitar(email:str=Form(...)):
    email=email.strip().lower()
    if email!=AUTHORIZED_EMAIL:
        return page('<section class="card"><h1>Acesso não autorizado</h1><p>Este e-mail não possui autorização.</p><a href="/">Voltar</a></section>')
    code=f"{secrets.randbelow(1_000_000):06d}"
    OTP_STORE[email]={"hash":hash_code(email,code),"exp":int(time.time())+OTP_TTL,"tries":0}
    try: send_otp(email,code)
    except Exception as e:
        print(f"ERRO_ENVIO_OTP: {type(e).__name__}: {e}",flush=True); OTP_STORE.pop(email,None)
        return page('<section class="card"><h1>Falha no envio</h1><p>Não foi possível enviar o código.</p><a href="/">Voltar</a></section>')
    return page(f"""<section class="card"><h1>Digite o código</h1><p>Enviamos um código para <b>{esc(email)}</b>.</p><form method="post" action="/validar-codigo"><input type="hidden" name="email" value="{esc(email)}"><label>Código de 6 dígitos</label><input name="code" minlength="6" maxlength="6" required><button>Entrar</button></form></section>""")

@app.post("/validar-codigo")
def validar(response:Response,email:str=Form(...),code:str=Form(...)):
    email=email.strip().lower(); rec=OTP_STORE.get(email)
    if not rec or rec["exp"]<int(time.time()) or rec["tries"]>=5:
        return page('<section class="card"><h1>Código inválido ou expirado</h1><a href="/">Solicitar novo</a></section>')
    rec["tries"]+=1
    if not hmac.compare_digest(rec["hash"],hash_code(email,code.strip())):
        return page('<section class="card"><h1>Código inválido</h1><a href="/">Tentar novamente</a></section>')
    OTP_STORE.pop(email,None)
    r=RedirectResponse("/processos",303)
    r.set_cookie("portically_processos_session",make_session(email),httponly=True,secure=True,samesite="strict",max_age=SESSION_TTL)
    return r

@app.get("/processos",response_class=HTMLResponse)
def processos(request:Request):
    if not auth(request): return RedirectResponse("/",303)
    return page(f"""<section class="card"><div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>Meus Processos</h1><p class="case-sub">Acompanhe cada caso com seus processos relacionados, documentos e prazos em um só lugar.</p></div><div class="header-meta"><span class="version-inline">v{APP_VERSION}</span><span class="version-inline">{UPDATE_LABEL}</span></div></div>
<div class="proc"><div class="chips"><span class="chip">JUSTIÇA DO TRABALHO</span><span class="chip amber">{MAIN["phase"].upper()}</span><span class="chip">1 VÍNCULO</span></div><h2 class="case-title">{TITLE}</h2><div class="cnj">{MAIN["cnj"]}</div><div class="case-footer"><div><div class="label">ORIGEM</div><p class="case-location">{MAIN["court"]} · {MAIN["unit"]}</p></div><a class="btn" href="/processos/{MAIN["cnj"]}?tab=resumo">Ver detalhes do caso</a></div></div><div class="actions"><form method="post" action="/sair"><button>Sair</button></form></div></section>""")

@app.get("/processos/{cnj}",response_class=HTMLResponse)
def detalhe(cnj:str,request:Request,tab:str="resumo"):
    if not auth(request): return RedirectResponse("/",303)
    if cnj not in (MAIN["cnj"],RELATED["cnj"]):
        return page('<section class="card"><h1>Processo não encontrado</h1><a class="btn" href="/processos">Voltar</a></section>')
    valid={"resumo","movimentacoes","documentos","relacionados","prazos","partes","validacao","historico"}
    if tab not in valid: tab="resumo"
    body=f"""<section class="card"><div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>{TITLE}</h1><div class="chips"><span class="chip">TRABALHISTA</span><span class="chip amber">{MAIN["phase"].upper()}</span><span class="chip">1 PROCESSO VINCULADO</span></div></div><div class="chips"><span class="chip green">v{APP_VERSION}</span><span class="chip">{UPDATE_LABEL}</span></div></div>
{tabs(tab)}{tab_content(tab)}
<div class="section"><h2>Controle de integridade</h2><div class="grid"><div class="box"><div class="label">Fonte oficial</div><div class="value">Obrigatória</div></div><div class="box"><div class="label">Correspondência CNJ</div><div class="value">Exata</div></div><div class="box"><div class="label">Documentos</div><div class="value">ID + fonte + captura + hash</div></div><div class="box"><div class="label">Status técnico</div><div class="value">Aguardando validação humana</div></div></div></div>
<div class="actions"><a class="btn" href="/processos">Voltar</a><form method="post" action="/sair"><button>Sair</button></form></div></section>"""
    return page(body,f"Processo {MAIN['cnj']}")

@app.post("/processos/{cnj}/validar")
def salvar_validacao(cnj:str,request:Request,
    cnj_ok:str=Form(None,alias="cnj"),
    tribunal:str=Form(None),partes:str=Form(None),vinculo:str=Form(None),
    documento:str=Form(None),prazo:str=Form(None),
    data_ciencia:str=Form(""),observacoes:str=Form("")):
    if not auth(request): return RedirectResponse("/",303)
    if cnj!=MAIN["cnj"]: return RedirectResponse("/processos",303)
    VALIDATION["cnj"]=bool(cnj_ok)
    VALIDATION["tribunal"]=bool(tribunal)
    VALIDATION["partes"]=bool(partes)
    VALIDATION["vinculo"]=bool(vinculo)
    VALIDATION["documento"]=bool(documento)
    VALIDATION["data_ciencia"]=data_ciencia.strip()
    VALIDATION["prazo"]=bool(prazo) and bool(data_ciencia.strip())
    VALIDATION["observacoes"]=observacoes.strip()
    now=datetime.now(timezone(timedelta(hours=-3)))
    VALIDATION["validated_at"]=now.strftime("%d/%m/%Y às %H:%M")
    VALIDATION["validated_by"]=AUTHORIZED_EMAIL
    return RedirectResponse(f"/processos/{MAIN['cnj']}?tab=validacao",303)

@app.post("/sair")
def sair():
    r=RedirectResponse("/",303); r.delete_cookie("portically_processos_session"); return r
