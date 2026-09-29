import os, time, secrets, hashlib, hmac, html
import resend
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

APP_VERSION="1.1.1"
UPDATE_LABEL="Atualização 07 · V7"
AUTHORIZED_EMAIL=os.environ.get("AUTHORIZED_EMAIL","").strip().lower()
SESSION_SECRET=os.environ.get("SESSION_SECRET","")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","").strip()
RESEND_FROM_EMAIL=os.environ.get("RESEND_FROM_EMAIL","acesso@processos.portically.com.br").strip()
resend.api_key=RESEND_API_KEY
OTP_TTL=600
SESSION_TTL=28800
OTP_STORE={}

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
.card{{background:var(--p);border:1px solid #20354f;border-radius:18px;padding:22px;box-shadow:0 20px 60px #0006}}h1{{font-size:30px;margin:.4rem 0 1rem}}h2{{font-size:19px;margin:0 0 14px}}h3{{font-size:16px;margin:0 0 8px}}p{{color:var(--muted);line-height:1.5}}
.brand{{font-size:12px;letter-spacing:.16em;color:#7fc5ff}}.top{{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}}.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}}
.chip{{display:inline-block;padding:6px 9px;border:1px solid #31516f;border-radius:999px;font-size:12px;color:#c9dbec;background:#0b1a2b}}.green{{border-color:#2e6942;color:#9cf0b8}}.amber{{border-color:#705d2a;color:#ffd77b}}
.tabs{{display:flex;gap:8px;overflow:auto;margin:18px 0}}.tab{{white-space:nowrap;padding:10px 12px;border-radius:9px;background:#0a1626;border:1px solid #223955;color:#c4d4e3;text-decoration:none;font-size:13px}}.tab.active{{background:#173c63;color:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.box,.proc{{padding:16px;border-radius:14px;background:var(--p2);border:1px solid var(--line)}}.section{{margin-top:18px}}
.label{{font-size:12px;color:#8fa5ba;text-transform:uppercase}}.value{{margin-top:6px;font-weight:700}}.cnj{{font-family:monospace;font-weight:700;word-break:break-word}}
.notice{{padding:13px;border-radius:12px;background:#0b2136;border:1px solid #295374;color:#c4d9ec;margin-bottom:14px}}.timeline{{border-left:2px solid #2f5271;margin-left:8px;padding-left:20px}}.event{{margin:0 0 18px}}
.link{{margin-left:8px;padding:12px 0 0 22px;border-left:2px solid #345c80;color:#a8bbce}}.deadline{{border-left:4px solid #ffc857}}
button,.btn{{display:inline-block;padding:12px 15px;border:0;border-radius:10px;background:#1f8cff;color:#fff;font-weight:700;text-decoration:none;cursor:pointer}}input{{width:100%;padding:14px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-size:16px}}label{{display:block;margin:18px 0 8px}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}}.actions form{{margin:0}}.actions form button{{background:#213247}}a{{color:#7fc5ff}}
.badge{{position:fixed;right:14px;bottom:14px;z-index:50;background:#10243a;border:1px solid #3a668f;border-radius:12px;padding:10px 12px;box-shadow:0 10px 30px #0008;display:flex;flex-direction:column;gap:2px}}.badge b{{font-size:12px}}.badge span{{font-size:11px;color:#8ec8ff}}.badge small{{font-size:10px;color:#8ca0b5}}
@media(max-width:600px){{main{{padding:12px 12px 92px}}.card{{padding:16px}}h1{{font-size:24px}}}}
</style></head><body>
<div class="badge"><b>Portically Processos v{APP_VERSION}</b><span>{UPDATE_LABEL}</span><small>Atualização atual</small></div>
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
           ("relacionados","Processos relacionados"),("prazos","Prazos"),("partes","Partes"),("historico","Histórico")]
    return '<div class="tabs">'+''.join(
      f'<a class="tab {"active" if k==active else ""}" href="/processos/{MAIN["cnj"]}?tab={k}">{label}</a>'
      for k,label in items)+'</div>'

def tab_content(tab):
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
<div class="box"><div class="label">Versão anterior</div><div class="value">v1.1.0 · Atualização 06 · V6</div><p>Agrupamento do caso e vínculo entre processo principal e carta precatória.</p></div></div>"""
    return f"""<div class="notice"><b>Leitura rápida:</b> Processo em fase de execução. Há uma carta precatória vinculada no TRT-21, em Natal/RN, destinada ao cumprimento de citação originada no processo principal de Fortaleza/CE.</div>
<div class="grid"><div class="box"><div class="label">Processo principal</div><div class="value cnj">{MAIN["cnj"]}</div></div><div class="box"><div class="label">Tribunal</div><div class="value">{MAIN["court"]}</div><p>{MAIN["unit"]}</p></div><div class="box"><div class="label">Fase</div><div class="value">{MAIN["phase"]}</div></div><div class="box"><div class="label">Sincronização</div><div class="value">{MAIN["sync"]}</div></div></div>
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
    return page(f"""<section class="card"><div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>Meus Processos</h1><p>Casos agrupados por vínculo.</p></div><div class="chips"><span class="chip green">v{APP_VERSION}</span><span class="chip">{UPDATE_LABEL}</span></div></div>
<div class="proc"><div class="chips"><span class="chip">TRABALHISTA</span><span class="chip amber">{MAIN["phase"].upper()}</span><span class="chip">1 PROCESSO VINCULADO</span></div><h2>{TITLE}</h2><div class="cnj">{MAIN["cnj"]}</div><p>{MAIN["court"]} · {MAIN["unit"]}</p><a class="btn" href="/processos/{MAIN["cnj"]}?tab=resumo">Abrir caso</a></div><div class="actions"><form method="post" action="/sair"><button>Sair</button></form></div></section>""")

@app.get("/processos/{cnj}",response_class=HTMLResponse)
def detalhe(cnj:str,request:Request,tab:str="resumo"):
    if not auth(request): return RedirectResponse("/",303)
    if cnj not in (MAIN["cnj"],RELATED["cnj"]):
        return page('<section class="card"><h1>Processo não encontrado</h1><a class="btn" href="/processos">Voltar</a></section>')
    valid={"resumo","movimentacoes","documentos","relacionados","prazos","partes","historico"}
    if tab not in valid: tab="resumo"
    body=f"""<section class="card"><div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>{TITLE}</h1><div class="chips"><span class="chip">TRABALHISTA</span><span class="chip amber">{MAIN["phase"].upper()}</span><span class="chip">1 PROCESSO VINCULADO</span></div></div><div class="chips"><span class="chip green">v{APP_VERSION}</span><span class="chip">{UPDATE_LABEL}</span></div></div>
{tabs(tab)}{tab_content(tab)}
<div class="section"><h2>Controle de integridade</h2><div class="grid"><div class="box"><div class="label">Fonte oficial</div><div class="value">Obrigatória</div></div><div class="box"><div class="label">Correspondência CNJ</div><div class="value">Exata</div></div><div class="box"><div class="label">Documentos</div><div class="value">ID + fonte + captura + hash</div></div><div class="box"><div class="label">Status técnico</div><div class="value">Aguardando validação humana</div></div></div></div>
<div class="actions"><a class="btn" href="/processos">Voltar</a><form method="post" action="/sair"><button>Sair</button></form></div></section>"""
    return page(body,f"Processo {MAIN['cnj']}")

@app.post("/sair")
def sair():
    r=RedirectResponse("/",303); r.delete_cookie("portically_processos_session"); return r
