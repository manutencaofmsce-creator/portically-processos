import os, time, secrets, hashlib, hmac, json, urllib.request
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

APP_VERSION="1.0.4"
AUTHORIZED_EMAIL=os.environ.get("AUTHORIZED_EMAIL","").strip().lower()
SESSION_SECRET=os.environ.get("SESSION_SECRET","")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","").strip()
RESEND_FROM_EMAIL=os.environ.get("RESEND_FROM_EMAIL","acesso@processos.portically.com.br").strip()
OTP_TTL=600
SESSION_TTL=28800
OTP_STORE={}

app=FastAPI(title="Portically Processos", docs_url=None, redoc_url=None)

def page(body:str,title:str="Portically Processos"):
    return HTMLResponse(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>
    body{{margin:0;font-family:Arial,sans-serif;background:#07111f;color:#e8eef7}}main{{min-height:100vh;display:grid;place-items:center;padding:24px}}.card{{width:min(920px,100%);background:#0d1b2e;border:1px solid #20354f;border-radius:20px;padding:28px;box-shadow:0 24px 80px #0008}}.brand{{font-size:13px;letter-spacing:.18em;color:#7fc5ff}}h1{{margin:.4rem 0 1rem;font-size:32px}}p{{color:#aebed0;line-height:1.55}}label{{display:block;margin:18px 0 8px}}input{{width:100%;box-sizing:border-box;padding:14px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:white;font-size:16px}}button{{margin-top:16px;width:100%;padding:14px;border:0;border-radius:10px;background:#1f8cff;color:white;font-weight:700;cursor:pointer}}.muted{{font-size:13px;color:#8ca0b5}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:18px}}.box{{padding:16px;border-radius:14px;background:#0a1626;border:1px solid #223955}}a{{color:#7fc5ff}}.err{{margin-top:14px;padding:12px;border-radius:10px;background:#3a1720;color:#ffc2ca}}.ok{{margin-top:14px;padding:12px;border-radius:10px;background:#12351f;color:#a7efba}}</style></head><body><main>{body}</main></body></html>""")

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
    payload=json.dumps({
        "from": f"Portically Processos <{RESEND_FROM_EMAIL}>",
        "to": [email],
        "subject": "Código de acesso — Portically Processos",
        "text": f"Seu código de acesso ao Portically Processos é: {code}\n\nEle expira em 10 minutos e só pode ser usado uma vez."
    }).encode("utf-8")
    req=urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"Resend HTTP {resp.status}")

@app.get("/health")
def health():
    return {"status":"ok","service":"portically-processos","version":APP_VERSION}

@app.get("/",response_class=HTMLResponse)
def login(request:Request):
    if valid_session(request.cookies.get("portically_processos_session","")):
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
    return page(f"""<section class="card"><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>Digite o código</h1><p>Enviamos um código temporário para <strong>{email}</strong>.</p><form method="post" action="/validar-codigo"><input type="hidden" name="email" value="{email}"><label>Código de 6 dígitos</label><input name="code" inputmode="numeric" minlength="6" maxlength="6" required autocomplete="one-time-code"><button>Entrar no Portically Processos</button></form></section>""")

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
    if not valid_session(request.cookies.get("portically_processos_session","")):
        return RedirectResponse("/",303)
    return page("""<section class="card"><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>Processo piloto</h1><p><strong>0800534-37.2025.8.20.5001</strong></p><div class="grid"><div class="box"><b>Status</b><p>Em validação</p></div><div class="box"><b>Sincronização oficial</b><p>Aguardando validação humana</p></div><div class="box"><b>Integridade documental</b><p>Aguardando documentos oficiais</p></div><div class="box"><b>Processos relacionados</b><p>Não validado</p></div></div><p class="muted">Somente fontes oficiais. Correspondência CNJ exata. Nenhum documento, andamento ou vínculo é criado por aproximação.</p><form method="post" action="/sair"><button>Sair</button></form></section>""")

@app.post("/sair")
def sair():
    r=RedirectResponse("/",303)
    r.delete_cookie("portically_processos_session")
    return r
