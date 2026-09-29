import os, time, secrets, hashlib, hmac, html
import resend
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

APP_VERSION="1.1.0"
BUILD_LABEL="Atualização 06 · V6"
AUTHORIZED_EMAIL=os.environ.get("AUTHORIZED_EMAIL","").strip().lower()
SESSION_SECRET=os.environ.get("SESSION_SECRET","")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","").strip()
RESEND_FROM_EMAIL=os.environ.get("RESEND_FROM_EMAIL","acesso@processos.portically.com.br").strip()
resend.api_key=RESEND_API_KEY
OTP_TTL=600
SESSION_TTL=28800
OTP_STORE={}

app=FastAPI(title="Portically Processos", docs_url=None, redoc_url=None)

CASE_DATA = {
    "title": "Francisco Fábio Dias da Silva x Portically Tecnologia Ltda. e outros",
    "summary": "Processo em fase de execução. Há uma carta precatória vinculada no TRT-21, em Natal/RN, destinada ao cumprimento de citação originada no processo principal de Fortaleza/CE.",
    "main": {
        "cnj": "0000678-55.2024.5.07.0001",
        "kind": "Processo principal",
        "justice": "Justiça do Trabalho",
        "court": "TRT-7",
        "unit": "1ª Vara do Trabalho de Fortaleza/CE",
        "state": "CE",
        "city": "Fortaleza",
        "phase": "Execução",
        "sync": "Aguardando validação humana",
        "source": "PJe / TRT-7",
    },
    "related": [{
        "cnj": "0000869-21.2026.5.21.0008",
        "kind": "Carta Precatória",
        "class": "CartPrecCiv",
        "justice": "Justiça do Trabalho",
        "court": "TRT-21",
        "unit": "8ª Vara do Trabalho de Natal/RN",
        "state": "RN",
        "city": "Natal",
        "purpose": "Citação",
        "origin": "0000678-55.2024.5.07.0001",
        "sync": "Aguardando validação humana",
        "source": "PJe / TRT-21",
    }],
    "parties": [
        {"role": "Autor / Exequente", "name": "Francisco Fábio Dias da Silva"},
        {"role": "Réu / Executado", "name": "Portically Tecnologia Ltda. e outros"},
        {"role": "Destinatária indicada no mandado", "name": "Fernanda Geroncio Pinheiro Dantas"},
    ],
    "deadlines": [{
        "label": "48 horas",
        "origin": "Mandado de Citação PJe-JT",
        "action": "Comprovar o pagamento do débito remanescente e, querendo, apresentar a medida processual indicada no mandado.",
        "status": "Data de início e vencimento ainda não validadas",
    }],
}

def page(body:str,title:str="Portically Processos"):
    return HTMLResponse(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>
    :root{{--bg:#07111f;--panel:#0d1b2e;--panel2:#0a1626;--line:#223955;--text:#e8eef7;--muted:#9fb1c4;--blue:#4da6ff;--green:#48d17a;--amber:#ffc857;--red:#ff6b7d}}
    *{{box-sizing:border-box}}body{{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:var(--text)}}main{{min-height:100vh;padding:24px}}.shell{{width:min(1180px,100%);margin:auto}}.card{{background:var(--panel);border:1px solid #20354f;border-radius:18px;padding:22px;box-shadow:0 20px 60px #0006}}.brand{{font-size:12px;letter-spacing:.16em;color:#7fc5ff}}h1{{margin:.45rem 0 1rem;font-size:30px}}h2{{font-size:19px;margin:0 0 14px}}h3{{font-size:16px;margin:0 0 8px}}p{{color:var(--muted);line-height:1.55}}label{{display:block;margin:18px 0 8px}}input{{width:100%;padding:14px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:white;font-size:16px}}button,.btn{{display:inline-block;padding:12px 15px;border:0;border-radius:10px;background:#1f8cff;color:white;font-weight:700;cursor:pointer;text-decoration:none}}form button{{width:100%;margin-top:16px}}a{{color:#7fc5ff}}.muted{{font-size:13px;color:#8ca0b5}}.err,.ok{{margin-top:14px;padding:12px;border-radius:10px}}.err{{background:#3a1720;color:#ffc2ca}}.ok{{background:#12351f;color:#a7efba}}
    .top{{display:flex;gap:16px;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;margin-bottom:18px}}.version{{font-size:12px;color:#8ca0b5;text-align:right}}.chips{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}.chip{{padding:6px 9px;border:1px solid #31516f;border-radius:999px;font-size:12px;color:#c9dbec;background:#0b1a2b}}.chip.amber{{border-color:#705d2a;color:#ffd77b}}.chip.green{{border-color:#2e6942;color:#9cf0b8}}
    .tabs{{display:flex;gap:8px;overflow:auto;margin:16px 0 20px;padding-bottom:4px}}.tab{{white-space:nowrap;padding:10px 12px;border-radius:9px;background:#0a1626;border:1px solid #223955;color:#c4d4e3;font-size:13px}}.tab.active{{background:#173c63;border-color:#2d6da8;color:white}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.box{{padding:16px;border-radius:14px;background:var(--panel2);border:1px solid var(--line)}}.box .label{{font-size:12px;color:#8fa5ba;text-transform:uppercase;letter-spacing:.05em}}.box .value{{margin-top:6px;font-weight:700}}.section{{margin-top:16px}}.process-card{{padding:16px;border-radius:14px;background:#0a1626;border:1px solid #28445f;margin-top:10px}}.process-head{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}.cnj{{font-family:monospace;font-size:16px;font-weight:700;color:#fff}}.linkline{{padding:12px 0 0 22px;margin-left:8px;border-left:2px solid #345c80;color:#a8bbce}}.deadline{{border-left:4px solid var(--amber)}}.timeline{{border-left:2px solid #2f5271;margin-left:8px;padding-left:20px}}.event{{position:relative;margin:0 0 18px}}.event:before{{content:"";position:absolute;left:-26px;top:5px;width:10px;height:10px;border-radius:50%;background:#4da6ff;border:2px solid #07111f}}.footer-actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}}.footer-actions form{{margin:0}}.footer-actions form button{{width:auto;margin:0;background:#213247}}@media(max-width:600px){{main{{padding:12px}}.card{{padding:16px}}h1{{font-size:24px}}}}
    </style></head><body><main><div class="shell">{body}</div></main></body></html>""")

def require_auth(request:Request):
    return valid_session(request.cookies.get("portically_processos_session",""))

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
    except:
        return False

def send_otp(email,code):
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY não configurada")
    return resend.Emails.send({
        "from": f"Portically Processos <{RESEND_FROM_EMAIL}>",
        "to": [email],
        "subject": "Código de acesso — Portically Processos",
        "text": f"Seu código de acesso ao Portically Processos é: {code}\n\nEle expira em 10 minutos e só pode ser usado uma vez."
    })

@app.get("/health")
def health():
    return {"status":"ok","service":"portically-processos","version":APP_VERSION,"build":BUILD_LABEL}

@app.get("/",response_class=HTMLResponse)
def login(request:Request):
    if require_auth(request):
        return RedirectResponse("/processos",303)
    return page("""<section class="card"><div class="brand">PORTICALLY HUB · MÓDULO PROCESSOS</div><h1>Acesso protegido</h1><p>Informe o e-mail autorizado. Um código temporário será enviado para confirmar sua identidade antes de liberar qualquer dado processual.</p><form method="post" action="/solicitar-codigo"><label>E-mail</label><input name="email" type="email" required autocomplete="email"><button>Enviar código de acesso</button></form><p class="muted">Nenhuma informação processual é exibida antes da autenticação válida.</p></section>""")

@app.post("/solicitar-codigo",response_class=HTMLResponse)
def solicitar(email:str=Form(...)):
    email=email.strip().lower()
    if email!=AUTHORIZED_EMAIL:
        return page("""<section class="card"><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>Acesso não autorizado</h1><div class="err">Este e-mail não possui autorização para acessar o módulo.</div><p><a href="/">Voltar</a></p></section>""", "Acesso não autorizado")
    code=f"{secrets.randbelow(1_000_000):06d}"
    OTP_STORE[email]={"hash":hash_code(email,code),"exp":int(time.time())+OTP_TTL,"tries":0}
    try:
        send_otp(email,code)
    except Exception as e:
        print(f"ERRO_ENVIO_OTP: {type(e).__name__}: {e}", flush=True)
        OTP_STORE.pop(email,None)
        return page("""<section class="card"><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>Falha no envio do código</h1><div class="err">Não foi possível enviar o código de acesso. A configuração do serviço de e-mail precisa ser revisada.</div><p><a href="/">Voltar</a></p></section>""")
    return page(f"""<section class="card"><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>Digite o código</h1><p>Enviamos um código temporário para <strong>{html.escape(email)}</strong>.</p><form method="post" action="/validar-codigo"><input type="hidden" name="email" value="{html.escape(email)}"><label>Código de 6 dígitos</label><input name="code" inputmode="numeric" minlength="6" maxlength="6" required autocomplete="one-time-code"><button>Entrar no Portically Processos</button></form></section>""")

@app.post("/validar-codigo")
def validar(response:Response,email:str=Form(...),code:str=Form(...)):
    email=email.strip().lower()
    rec=OTP_STORE.get(email)
    if not rec or rec["exp"]<int(time.time()) or rec["tries"]>=5:
        return page("""<section class="card"><h1>Código inválido ou expirado</h1><p><a href="/">Solicitar novo código</a></p></section>""")
    rec["tries"]+=1
    if not hmac.compare_digest(rec["hash"],hash_code(email,code.strip())):
        return page("""<section class="card"><h1>Código inválido</h1><p><a href="/">Tentar novamente</a></p></section>""")
    OTP_STORE.pop(email,None)
    r=RedirectResponse("/processos",303)
    r.set_cookie("portically_processos_session",make_session(email),httponly=True,secure=True,samesite="strict",max_age=SESSION_TTL)
    return r

@app.get("/processos",response_class=HTMLResponse)
def processos(request:Request):
    if not require_auth(request):
        return RedirectResponse("/",303)
    main=CASE_DATA["main"]
    related=CASE_DATA["related"]
    body=f"""<section class="card">
    <div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>Meus Processos</h1><p>Casos agrupados por vínculo, sem contar cartas precatórias e incidentes como novas ações independentes.</p></div><div class="version">v{APP_VERSION}<br>{BUILD_LABEL}</div></div>
    <div class="process-card"><div class="process-head"><div><div class="chips"><span class="chip">TRABALHISTA</span><span class="chip amber">{html.escape(main["phase"].upper())}</span><span class="chip">{len(related)} PROCESSO VINCULADO</span></div><h2>{html.escape(CASE_DATA["title"])}</h2><div class="cnj">{main["cnj"]}</div><p>{html.escape(main["court"])} · {html.escape(main["unit"])}</p></div><div><a class="btn" href="/processos/{main["cnj"]}">Abrir caso</a></div></div></div>
    <div class="footer-actions"><form method="post" action="/sair"><button>Sair</button></form></div>
    </section>"""
    return page(body)

@app.get("/processos/{cnj}",response_class=HTMLResponse)
def processo_detalhe(cnj:str,request:Request):
    if not require_auth(request):
        return RedirectResponse("/",303)
    main=CASE_DATA["main"]
    related=CASE_DATA["related"]
    if cnj!=main["cnj"] and cnj not in [x["cnj"] for x in related]:
        return page("""<section class="card"><h1>Processo não encontrado</h1><p>O número informado não pertence aos casos cadastrados nesta versão.</p><a class="btn" href="/processos">Voltar</a></section>""","Processo não encontrado")
    rel=related[0]
    related_html=f"""<div class="process-card"><div class="process-head"><div><span class="chip">CARTA PRECATÓRIA</span><h3 style="margin-top:10px">{rel["cnj"]}</h3><p>{html.escape(rel["court"])} · {html.escape(rel["unit"])}</p></div><div><span class="chip amber">{html.escape(rel["sync"])}</span></div></div><div class="grid"><div class="box"><div class="label">Finalidade</div><div class="value">{html.escape(rel["purpose"])}</div></div><div class="box"><div class="label">Processo de origem</div><div class="value">{rel["origin"]}</div></div><div class="box"><div class="label">Fonte</div><div class="value">{html.escape(rel["source"])}</div></div></div></div>"""
    parties_html="".join([f'<div class="box"><div class="label">{html.escape(p["role"])}</div><div class="value">{html.escape(p["name"])}</div></div>' for p in CASE_DATA["parties"]])
    deadlines_html="".join([f'<div class="box deadline"><div class="label">{html.escape(d["origin"])}</div><div class="value">{html.escape(d["label"])}</div><p>{html.escape(d["action"])}</p><div class="muted">{html.escape(d["status"])}</div></div>' for d in CASE_DATA["deadlines"]])
    body=f"""<section class="card">
    <div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>{html.escape(CASE_DATA["title"])}</h1><div class="chips"><span class="chip">TRABALHISTA</span><span class="chip amber">{html.escape(main["phase"].upper())}</span><span class="chip">{len(related)} PROCESSO VINCULADO</span></div></div><div class="version">v{APP_VERSION}<br>{BUILD_LABEL}</div></div>
    <div class="tabs"><div class="tab active">Resumo</div><div class="tab">Movimentações</div><div class="tab">Documentos</div><div class="tab">Processos relacionados</div><div class="tab">Prazos</div><div class="tab">Partes</div><div class="tab">Histórico</div></div>

    <div class="section"><h2>Resumo do caso</h2><p>{html.escape(CASE_DATA["summary"])}</p></div>
    <div class="grid">
      <div class="box"><div class="label">Processo principal</div><div class="value cnj">{main["cnj"]}</div></div>
      <div class="box"><div class="label">Tribunal</div><div class="value">{html.escape(main["court"])}</div><p>{html.escape(main["unit"])}</p></div>
      <div class="box"><div class="label">Fase identificada</div><div class="value">{html.escape(main["phase"])}</div></div>
      <div class="box"><div class="label">Sincronização</div><div class="value">{html.escape(main["sync"])}</div></div>
    </div>

    <div class="section"><h2>Entenda este processo</h2><div class="grid"><div class="box"><h3>Execução</h3><p>Fase em que o Judiciário busca o cumprimento da obrigação ou pagamento determinado no processo.</p></div><div class="box"><h3>Por que há um processo em Natal?</h3><p>O processo principal tramita em Fortaleza/CE. Foi criada uma carta precatória no TRT-21 para cumprir uma diligência em Natal/RN.</p></div><div class="box"><h3>Carta Precatória</h3><p>É o instrumento usado para pedir a outro juízo que cumpra uma diligência fora da área do processo principal.</p></div></div></div>

    <div class="section"><h2>Relação entre processos</h2>
      <div class="process-card"><span class="chip green">PROCESSO PRINCIPAL</span><h3 style="margin-top:10px">{main["cnj"]}</h3><p>{html.escape(main["court"])} · {html.escape(main["unit"])}</p></div>
      <div class="linkline">gerou uma Carta Precatória para cumprimento de citação em Natal/RN</div>
      {related_html}
    </div>

    <div class="section"><h2>Prazos identificados</h2><div class="grid">{deadlines_html}</div><p class="muted">O sistema não calcula vencimento definitivo até que a data de ciência/citação e a regra de contagem sejam validadas.</p></div>
    <div class="section"><h2>Partes e pessoas relacionadas</h2><div class="grid">{parties_html}</div></div>

    <div class="section"><h2>Linha do tempo inicial</h2><div class="timeline">
      <div class="event"><h3>Processo principal · TRT-7</h3><p>Processo nº {main["cnj"]}, em Fortaleza/CE.</p></div>
      <div class="event"><h3>Carta Precatória · TRT-21</h3><p>Processo nº {rel["cnj"]}, em Natal/RN, vinculado ao processo principal.</p></div>
      <div class="event"><h3>Mandado de citação</h3><p>Documento identificado com referência a prazo de 48 horas. Início e vencimento permanecem pendentes de validação.</p></div>
    </div></div>

    <div class="section"><h2>Controle de integridade</h2><div class="grid"><div class="box"><div class="label">Fonte oficial</div><div class="value">Obrigatória</div></div><div class="box"><div class="label">Correspondência CNJ</div><div class="value">Exata</div></div><div class="box"><div class="label">Documentos</div><div class="value">ID + fonte + captura + hash</div></div><div class="box"><div class="label">Status técnico</div><div class="value">Aguardando validação humana</div></div></div></div>

    <div class="footer-actions"><a class="btn" href="/processos">Voltar aos processos</a><form method="post" action="/sair"><button>Sair</button></form></div>
    </section>"""
    return page(body, f"Processo {main['cnj']}")

@app.post("/sair")
def sair():
    r=RedirectResponse("/",303)
    r.delete_cookie("portically_processos_session")
    return r
