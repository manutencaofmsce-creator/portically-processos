import os, time, secrets, hashlib, hmac, html, re
from datetime import datetime, timezone, timedelta
import resend
import psycopg
from cryptography.fernet import Fernet
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

APP_VERSION="1.2.5"
UPDATE_LABEL="Atualização 15 · V15"
AUTHORIZED_EMAIL=os.environ.get("AUTHORIZED_EMAIL","").strip().lower()
SESSION_SECRET=os.environ.get("SESSION_SECRET","")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","").strip()
RESEND_FROM_EMAIL=os.environ.get("RESEND_FROM_EMAIL","acesso@processos.portically.com.br").strip()
DATABASE_URL=os.environ.get("DATABASE_URL","").strip()
DATA_ENCRYPTION_KEY=os.environ.get("DATA_ENCRYPTION_KEY","").strip()
DATA_HMAC_KEY=os.environ.get("DATA_HMAC_KEY","").strip()
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
.mainnav{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 20px;padding:10px;background:#081522;border:1px solid #1e3a55;border-radius:12px}}.mainnav a{{text-decoration:none;padding:9px 12px;border-radius:9px;color:#c8d8e7;background:#0d2033;border:1px solid #244761;font-size:13px;font-weight:700}}.mainnav a:hover{{background:#14314d;border-color:#3d7197}}.mainnav .home{{background:#173c63;border-color:#2f6b9f;color:#fff}}.tabs{{display:flex;gap:8px;overflow:auto;margin:18px 0}}.tab{{white-space:nowrap;padding:10px 12px;border-radius:9px;background:#0a1626;border:1px solid #223955;color:#c4d4e3;text-decoration:none;font-size:13px}}.tab.active{{background:#173c63;color:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.dash{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:20px 0}}.dash-card{{display:block;text-decoration:none;padding:18px;border-radius:16px;background:linear-gradient(180deg,#0b1d31,#081522);border:1px solid #254866;color:#e8eef7}}.dash-label{{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#8fa7bc}}.dash-num{{font-size:34px;font-weight:800;margin:8px 0 4px}}.dash-link{{font-size:13px;color:#77bdff}}.empty{{padding:24px;text-align:center;border:1px dashed #2b4e6c;border-radius:15px;background:#081522;color:#93a9be}}.box{{padding:16px;border-radius:14px;background:#091726;border:1px solid #1e3852}}.proc{{padding:20px;border-radius:16px;background:linear-gradient(180deg,#0a192a,#081522);border:1px solid #254561;box-shadow:inset 0 1px 0 #ffffff08}}.section{{margin-top:20px}}.case-title{{max-width:850px}}.case-sub{{margin:.2rem 0 0}}.case-footer{{display:flex;justify-content:space-between;gap:16px;align-items:end;flex-wrap:wrap;margin-top:16px;padding-top:16px;border-top:1px solid #183149}}.case-location{{margin:0;color:#86a7c5}}
.label{{font-size:12px;color:#8fa5ba;text-transform:uppercase}}.value{{margin-top:6px;font-weight:700}}.cnj{{font-family:monospace;font-weight:700;word-break:break-word}}
.notice{{padding:13px;border-radius:12px;background:#0b2136;border:1px solid #295374;color:#c4d9ec;margin-bottom:14px}}.timeline{{border-left:2px solid #2f5271;margin-left:8px;padding-left:20px}}.event{{margin:0 0 18px}}
.link{{margin-left:8px;padding:12px 0 0 22px;border-left:2px solid #345c80;color:#a8bbce}}.deadline{{border-left:4px solid #ffc857}}.validate-card{{padding:18px;border:1px solid #2b4e6c;border-radius:15px;background:#091827;margin-bottom:12px}}.step{{display:grid;grid-template-columns:42px 1fr auto;gap:14px;align-items:start}}.stepn{{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#173c63;border:1px solid #2f6b9f;font-weight:700}}.checkrow{{display:flex;align-items:center;gap:8px;color:#dce9f5;font-weight:700;white-space:nowrap}}.checkrow input{{width:18px;height:18px;margin:0}}.help{{font-size:13px;color:#8fa7bc;margin-top:6px}}.progress{{height:9px;background:#07111f;border:1px solid #203a54;border-radius:999px;overflow:hidden;margin:10px 0}}.progress i{{display:block;height:100%;background:#2f9b5f}}.status-ok{{color:#9cf0b8}}.status-part{{color:#ffd77b}}.status-pend{{color:#9fb1c4}}textarea{{width:100%;min-height:88px;padding:12px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-family:Arial,sans-serif}}select{{width:100%;padding:14px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-size:16px}}.form-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.radar-row{{display:grid;grid-template-columns:1.2fr .8fr .8fr .7fr auto;gap:12px;align-items:center;padding:14px 0;border-bottom:1px solid #173149}}.radar-row:last-child{{border-bottom:0}}.tiny{{font-size:12px;color:#8fa7bc}}.danger{{background:#5b2430!important}}
button,.btn{{display:inline-block;padding:12px 15px;border:0;border-radius:10px;background:#1f8cff;color:#fff;font-weight:700;text-decoration:none;cursor:pointer}}input{{width:100%;padding:14px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-size:16px}}input[type="text"],input[type="search"],input[type="tel"],textarea{{text-transform:uppercase}}input[type="email"]{{text-transform:lowercase}}label{{display:block;margin:18px 0 8px}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}}.actions form{{margin:0}}.actions form button{{background:#213247}}a{{color:#7fc5ff}}
.badge{{position:fixed;right:14px;bottom:14px;z-index:50;background:#0b1c2d;border:1px solid #315776;border-radius:11px;padding:8px 11px;box-shadow:0 10px 30px #0008;display:flex;align-items:center;gap:7px}}.badge b{{font-size:11px}}.badge span{{font-size:10px;color:#8ec8ff}}.badge small{{display:none}}
@media(max-width:600px){{main{{padding:12px 12px 92px}}.card{{padding:16px}}h1{{font-size:24px}}}}
</style>
<script>
document.addEventListener("input",function(e){{
  const el=e.target;
  if(el.matches('input[type="email"]')){{
    const s=el.selectionStart, t=el.selectionEnd;
    el.value=el.value.toLowerCase();
    try{{el.setSelectionRange(s,t)}}catch(_){{}}
    return;
  }}
  if(el.matches('input[type="text"],input[type="search"],input[type="tel"],textarea')){{
    const s=el.selectionStart, t=el.selectionEnd;
    el.value=el.value.toLocaleUpperCase("pt-BR");
    try{{el.setSelectionRange(s,t)}}catch(_){{}}
  }}
}});
</script></head><body>
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

def main_nav():
    return """<nav class="mainnav">
    <a class="home" href="/painel">Painel principal</a>
    <a href="/processos">Processos</a>
    <a href="/radar">Radar</a>
    <a href="/movimentacoes">Movimentações</a>
    <a href="/novos-processos">Novos processos</a>
    <a href="/alertas">Alertas</a>
    </nav>"""

def app_header(title,subtitle=""):
    sub=f'<p class="case-sub">{esc(subtitle)}</p>' if subtitle else ""
    return f"""<div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>{esc(title)}</h1>{sub}</div><div class="header-meta"><span class="version-inline">v{APP_VERSION}</span><span class="version-inline">{UPDATE_LABEL}</span></div></div>{main_nav()}"""

def only_digits(v):
    return "".join(ch for ch in str(v) if ch.isdigit())

def valid_cpf(v):
    n=only_digits(v)
    if len(n)!=11 or n==n[0]*11: return False
    for size in (9,10):
        s=sum(int(n[i])*(size+1-i) for i in range(size))
        d=(s*10)%11
        if d==10: d=0
        if d!=int(n[size]): return False
    return True

def valid_cnpj(v):
    n=only_digits(v)
    if len(n)!=14 or n==n[0]*14: return False
    def calc(base,weights):
        s=sum(int(a)*b for a,b in zip(base,weights))
        r=s%11
        return "0" if r<2 else str(11-r)
    d1=calc(n[:12],[5,4,3,2,9,8,7,6,5,4,3,2])
    d2=calc(n[:12]+d1,[6,5,4,3,2,9,8,7,6,5,4,3,2])
    return n[-2:]==d1+d2

def valid_email(value):
    v=str(value).strip().lower()
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",v))

def mask_email(value):
    v=str(value).strip().lower()
    if "@" not in v: return "—"
    local,domain=v.split("@",1)
    visible=local[:2] if len(local)>=2 else local[:1]
    return f"{visible}***@{domain}"

def valid_whatsapp(value):
    n=only_digits(value)
    return 10 <= len(n) <= 13

def normalize_whatsapp(value):
    n=only_digits(value)
    if len(n) in (10,11):
        n="55"+n
    return n

def mask_whatsapp(value):
    n=normalize_whatsapp(value)
    if len(n)>=12:
        return f"+{n[:2]} (***) *****-{n[-4:]}"
    return "Não informado"

def encrypt_value(value):
    return crypto_box().encrypt(str(value).encode()).decode()

def mask_doc(kind,value):
    n=only_digits(value)
    if kind=="CPF" and len(n)==11: return f"{n[:3]}.***.***-{n[-2:]}"
    if kind=="CNPJ" and len(n)==14: return f"{n[:2]}.***.***/****-{n[-2:]}"
    return "Documento inválido"

def db_ready():
    return bool(DATABASE_URL and DATA_ENCRYPTION_KEY and DATA_HMAC_KEY)

def db_conn():
    return psycopg.connect(DATABASE_URL, autocommit=True)

def crypto_box():
    return Fernet(DATA_ENCRYPTION_KEY.encode())

def doc_fingerprint(value):
    return hmac.new(DATA_HMAC_KEY.encode(),only_digits(value).encode(),hashlib.sha256).hexdigest()

def encrypt_doc(value):
    return crypto_box().encrypt(only_digits(value).encode()).decode()

def init_db():
    if not db_ready(): return
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS radar_items(
                id TEXT PRIMARY KEY,
                tipo TEXT NOT NULL CHECK (tipo IN ('CPF','CNPJ')),
                nome TEXT NOT NULL,
                doc_cipher TEXT NOT NULL,
                doc_hash TEXT NOT NULL UNIQUE,
                mascara TEXT NOT NULL,
                frequencia TEXT NOT NULL,
                email_alerta BOOLEAN NOT NULL DEFAULT FALSE,
                whatsapp_alerta BOOLEAN NOT NULL DEFAULT FALSE,
                status TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
            cur.execute("ALTER TABLE radar_items ADD COLUMN IF NOT EXISTS whatsapp_cipher TEXT")
            cur.execute("ALTER TABLE radar_items ADD COLUMN IF NOT EXISTS whatsapp_mask TEXT")
            cur.execute("ALTER TABLE radar_items ADD COLUMN IF NOT EXISTS email_cipher TEXT")
            cur.execute("ALTER TABLE radar_items ADD COLUMN IF NOT EXISTS email_mask TEXT")
            cur.execute("""CREATE TABLE IF NOT EXISTS audit_log(
                id BIGSERIAL PRIMARY KEY,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                details TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")

def audit(action,entity_type,entity_id="",details=""):
    if not db_ready(): return
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO audit_log(action,entity_type,entity_id,details) VALUES (%s,%s,%s,%s)",
                        (action,entity_type,entity_id,details[:1000]))

def list_radar_items():
    if not db_ready(): return []
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,tipo,nome,mascara,frequencia,email_alerta,whatsapp_alerta,status,created_at,whatsapp_mask,email_mask
                           FROM radar_items ORDER BY created_at DESC""")
            rows=cur.fetchall()
    items=[]
    for r in rows:
        canais=[]
        if r[5]: canais.append("E-mail")
        if r[6]: canais.append("WhatsApp")
        items.append({"id":r[0],"tipo":r[1],"nome":r[2],"mascara":r[3],"frequencia":r[4],
                      "canais":", ".join(canais) if canais else "Somente sistema","status":r[7],"created_at":r[8],"whatsapp":r[9] or "—","email":r[10] or "—"})
    return items

@app.on_event("startup")
def startup():
    init_db()

@app.middleware("http")
async def security_headers(request,call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"]="no-store, max-age=0"
    response.headers["Content-Security-Policy"]="default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response

def dashboard_counts():
    try:
        radar_count=len(list_radar_items())
    except Exception:
        radar_count=0
    return {"processos":1,"cpf_cnpj":radar_count,"movimentacoes":0,"novos_processos":0,"alertas":0,"validacoes":1 if validation_status()[1] < 6 else 0}

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
<div class="box"><div class="label">Versão anterior</div><div class="value">v1.2.4 · Atualização 14 · V14</div><p>Agrupamento do caso e vínculo entre processo principal e carta precatória.</p></div></div>"""
    return f"""<div class="notice"><b>Leitura rápida:</b> Processo em fase de execução. Há uma carta precatória vinculada no TRT-21, em Natal/RN, destinada ao cumprimento de citação originada no processo principal de Fortaleza/CE.</div>
<div class="grid"><div class="box"><div class="label">Processo principal</div><div class="value cnj">{MAIN["cnj"]}</div></div><div class="box"><div class="label">Tribunal</div><div class="value">{MAIN["court"]}</div><p>{MAIN["unit"]}</p></div><div class="box"><div class="label">Fase</div><div class="value">{MAIN["phase"]}</div></div><div class="box"><div class="label">Sincronização</div><div class="value">{validation_status()[0]}</div><p>{validation_status()[1]} de 6 itens confirmados</p><a class="btn" href="/processos/{MAIN["cnj"]}?tab=validacao">Iniciar validação</a></div></div>
<div class="section"><h2>Entenda este processo</h2><div class="grid"><div class="box"><h3>Execução</h3><p>Fase em que o Judiciário busca o cumprimento da obrigação ou pagamento indicado no processo.</p></div><div class="box"><h3>Por que há um processo em Natal?</h3><p>O processo principal tramita em Fortaleza/CE. A carta precatória foi aberta no TRT-21 para cumprir uma diligência em Natal/RN.</p></div><div class="box"><h3>Carta Precatória</h3><p>É o instrumento usado para pedir a outro juízo que cumpra uma diligência fora da área do processo principal.</p></div></div></div>"""

@app.get("/health")
def health():
    return {"status":"ok","service":"portically-processos","version":APP_VERSION,"update":UPDATE_LABEL,"database":"connected" if db_ready() else "not-linked"}

@app.get("/",response_class=HTMLResponse)
def login(request:Request):
    if auth(request): return RedirectResponse("/painel",303)
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
    r=RedirectResponse("/painel",303)
    r.set_cookie("portically_processos_session",make_session(email),httponly=True,secure=True,samesite="strict",max_age=SESSION_TTL)
    return r

@app.get("/painel",response_class=HTMLResponse)
def painel(request:Request):
    if not auth(request): return RedirectResponse("/",303)
    n=dashboard_counts()
    status,done,css=validation_status()
    body=f"""<section class="card">{app_header("Painel","Acesse rapidamente processos, cadastros, movimentações, alertas e validações.")}
<div class="dash">
<a class="dash-card" href="/processos"><div class="dash-label">Processos monitorados</div><div class="dash-num">{n["processos"]}</div><div class="dash-link">Ver processos →</div></a>
<a class="dash-card" href="/radar"><div class="dash-label">CPF/CNPJ monitorados</div><div class="dash-num">{n["cpf_cnpj"]}</div><div class="dash-link">Abrir Radar →</div></a>
<a class="dash-card" href="/movimentacoes"><div class="dash-label">Novas movimentações</div><div class="dash-num">{n["movimentacoes"]}</div><div class="dash-link">Analisar →</div></a>
<a class="dash-card" href="/novos-processos"><div class="dash-label">Novos processos</div><div class="dash-num">{n["novos_processos"]}</div><div class="dash-link">Ver encontrados →</div></a>
<a class="dash-card" href="/alertas"><div class="dash-label">Alertas</div><div class="dash-num">{n["alertas"]}</div><div class="dash-link">Ver alertas →</div></a>
<a class="dash-card" href="/processos/{MAIN["cnj"]}?tab=validacao"><div class="dash-label">Validações pendentes</div><div class="dash-num">{n["validacoes"]}</div><div class="dash-link">Continuar validação →</div></a>
</div>
<div class="section"><h2>Resumo atual</h2><div class="grid"><div class="box"><div class="label">Caso em acompanhamento</div><div class="value">{TITLE}</div><p class="cnj">{MAIN["cnj"]}</p></div><div class="box"><div class="label">Status da validação</div><div class="value {css}">{status}</div><p>{done} de 6 itens confirmados</p></div><div class="box"><div class="label">Radar processual</div><div class="value">Ainda não configurado</div><p>Cadastre CPF/CNPJ para preparar a busca de novos processos nas fontes compatíveis.</p></div></div></div>
<div class="actions"><form method="post" action="/sair"><button>Sair</button></form></div></section>"""
    return page(body,"Painel · Portically Processos")

@app.get("/radar",response_class=HTMLResponse)
def radar(request:Request,msg:str=""):
    if not auth(request): return RedirectResponse("/",303)
    items=list_radar_items() if db_ready() else []
    rows=""
    for item in items:
        rows+=f"""<div class="radar-row"><div><div class="value">{esc(item["nome"])}</div><div class="tiny">{item["tipo"]} · {esc(item["mascara"])}</div></div><div><div class="label">Frequência</div><div>{esc(item["frequencia"])}</div></div><div><div class="label">Alertas</div><div>{esc(item["canais"])}</div><div class="tiny">E-mail: {esc(item["email"])}</div><div class="tiny">WhatsApp: {esc(item["whatsapp"])}</div></div><div><span class="chip amber">{esc(item["status"])}</span></div><form method="post" action="/radar/{item["id"]}/excluir"><button class="danger" type="submit">Excluir</button></form></div>"""
    if not rows:
        rows='<div class="empty">Nenhum CPF ou CNPJ cadastrado.</div>'
    notice=f'<div class="notice">{esc(msg)}</div>' if msg else ''
    body=f"""<section class="card">{app_header("Radar Processual","Cadastre CPF/CNPJ para acompanhar possíveis novos processos e alertas nas fontes compatíveis.")}
{notice}
{'' if db_ready() else '<div class="notice"><b>Banco seguro ainda não vinculado ao serviço.</b> O cadastro fica bloqueado para evitar armazenar CPF/CNPJ em memória temporária.</div>'}
<div class="notice"><b>Como funciona:</b> o cadastro abaixo cria o alvo de monitoramento. A busca automática nas fontes oficiais será ativada conforme cada fonte permitir pesquisa por CPF/CNPJ. CAPTCHA, login e restrições não serão contornados.</div>
<div class="proc"><h2>Novo monitoramento</h2>
<form method="post" action="/radar/adicionar"><div class="form-grid">
<div><label>Tipo</label><select name="tipo" required><option>CPF</option><option>CNPJ</option></select></div>
<div><label>Nome / Razão social</label><input name="nome" required placeholder="Identificação do titular"></div>
<div><label>CPF/CNPJ</label><input name="documento" required inputmode="numeric" placeholder="Somente números ou formatado"></div>
<div><label>Frequência</label><select name="frequencia"><option>Diária</option><option>Semanal</option><option>Manual</option></select></div>
</div>
<div class="form-grid">
<div><label><input type="checkbox" name="email_alerta" value="1" style="width:auto"> Avisar por e-mail</label><input type="email" name="email_alerta_endereco" autocomplete="email" placeholder="exemplo@dominio.com"><div class="tiny">O e-mail será convertido automaticamente para letras minúsculas e armazenado criptografado.</div></div>
<div><label><input type="checkbox" name="whatsapp_alerta" value="1" style="width:auto"> Avisar por WhatsApp</label><input name="whatsapp_numero" inputmode="tel" placeholder="Ex.: 84 99999-9999"><div class="tiny">Informe o número que receberá os alertas. Será armazenado criptografado.</div></div>
</div><button type="submit">Adicionar ao Radar</button></form></div>
<div class="section"><h2>Monitorados · {len(items)}</h2><div class="proc">{rows}</div></div>
<div class="actions"><a class="btn" href="/painel">Voltar ao painel</a></div></section>"""
    return page(body,"Radar Processual")

@app.post("/radar/adicionar")
def radar_adicionar(request:Request,tipo:str=Form(...),nome:str=Form(...),documento:str=Form(...),frequencia:str=Form("Diária"),email_alerta:str=Form(None),email_alerta_endereco:str=Form(""),whatsapp_alerta:str=Form(None),whatsapp_numero:str=Form("")):
    if not auth(request): return RedirectResponse("/",303)
    tipo=tipo.strip().upper()
    nome=nome.strip().upper()
    email_alerta_endereco=email_alerta_endereco.strip().lower()
    numero=only_digits(documento)
    ok=(tipo=="CPF" and valid_cpf(numero)) or (tipo=="CNPJ" and valid_cnpj(numero))
    if not ok:
        return RedirectResponse("/radar?msg=CPF/CNPJ inválido. Confira os números e tente novamente.",303)
    if email_alerta and not valid_email(email_alerta_endereco):
        return RedirectResponse("/radar?msg=Informe um e-mail válido para ativar os alertas por e-mail.",303)
    if whatsapp_alerta and not valid_whatsapp(whatsapp_numero):
        return RedirectResponse("/radar?msg=Informe um número de WhatsApp válido para ativar os alertas.",303)
    if not db_ready():
        return RedirectResponse("/radar?msg=Banco seguro ainda não está vinculado ao serviço. O cadastro não foi gravado.",303)
    item_id=secrets.token_hex(8)
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO radar_items(id,tipo,nome,doc_cipher,doc_hash,mascara,frequencia,email_alerta,whatsapp_alerta,status,whatsapp_cipher,whatsapp_mask,email_cipher,email_mask)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (item_id,tipo,nome,encrypt_doc(numero),doc_fingerprint(numero),mask_doc(tipo,numero),frequencia,
                             bool(email_alerta),bool(whatsapp_alerta),"Aguardando integração",
                             encrypt_value(normalize_whatsapp(whatsapp_numero)) if whatsapp_alerta else None,
                             mask_whatsapp(whatsapp_numero) if whatsapp_alerta else None,
                             encrypt_value(email_alerta_endereco) if email_alerta else None,
                             mask_email(email_alerta_endereco) if email_alerta else None))
        audit("CREATE","radar_item",item_id,f"{tipo} {mask_doc(tipo,numero)}")
    except Exception:
        return RedirectResponse("/radar?msg=Este documento já está cadastrado ou ocorreu uma falha segura no banco.",303)
    return RedirectResponse("/radar?msg=Monitoramento cadastrado com criptografia e persistência.",303)

@app.post("/radar/{item_id}/excluir")
def radar_excluir(item_id:str,request:Request):
    if not auth(request): return RedirectResponse("/",303)
    if not db_ready():
        return RedirectResponse("/radar?msg=Banco seguro indisponível.",303)
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM radar_items WHERE id=%s",(item_id,))
    audit("DELETE","radar_item",item_id,"Monitoramento removido")
    return RedirectResponse("/radar?msg=Monitoramento removido do banco.",303)

@app.get("/movimentacoes",response_class=HTMLResponse)
def movimentacoes_central(request:Request):
    if not auth(request): return RedirectResponse("/",303)
    return page(f"""<section class="card">{app_header("Novas movimentações","Itens novos detectados e ainda não analisados.")}<div class="empty">Nenhuma nova movimentação detectada automaticamente.</div><div class="section"><a class="btn" href="/processos/{MAIN["cnj"]}?tab=movimentacoes">Ver movimentações já catalogadas</a></div><div class="actions"><a class="btn" href="/painel">Voltar ao painel</a></div></section>""","Novas movimentações")

@app.get("/novos-processos",response_class=HTMLResponse)
def novos_processos(request:Request):
    if not auth(request): return RedirectResponse("/",303)
    return page(f"""<section class="card">{app_header("Novos processos encontrados","Resultados aguardando confirmação antes de entrar na base.")}<div class="empty">Nenhum novo processo encontrado pelo Radar.</div><div class="actions"><a class="btn" href="/radar">Abrir Radar</a><a class="btn" href="/painel">Voltar ao painel</a></div></section>""","Novos processos")

@app.get("/alertas",response_class=HTMLResponse)
def alertas(request:Request):
    if not auth(request): return RedirectResponse("/",303)
    return page(f"""<section class="card">{app_header("Alertas","Central de citações, intimações, prazos, audiências e ocorrências relevantes.")}<div class="empty">Nenhum alerta automático ativo.</div><div class="section"><div class="grid"><div class="box"><div class="label">Urgente</div><div class="value">Citação, intimação, prazo, audiência, bloqueio</div></div><div class="box"><div class="label">Importante</div><div class="value">Decisão, despacho, documento novo</div></div><div class="box"><div class="label">Informativo</div><div class="value">Atualizações administrativas</div></div></div></div><div class="actions"><a class="btn" href="/painel">Voltar ao painel</a></div></section>""","Alertas")

@app.get("/processos",response_class=HTMLResponse)
def processos(request:Request):
    if not auth(request): return RedirectResponse("/",303)
    return page(f"""<section class="card">{app_header("Meus Processos","Acompanhe cada caso com seus processos relacionados, documentos e prazos em um só lugar.")}
<div class="proc"><div class="chips"><span class="chip">JUSTIÇA DO TRABALHO</span><span class="chip amber">{MAIN["phase"].upper()}</span><span class="chip">1 VÍNCULO</span></div><h2 class="case-title">{TITLE}</h2><div class="cnj">{MAIN["cnj"]}</div><div class="case-footer"><div><div class="label">ORIGEM</div><p class="case-location">{MAIN["court"]} · {MAIN["unit"]}</p></div><a class="btn" href="/processos/{MAIN["cnj"]}?tab=resumo">Ver detalhes do caso</a></div></div><div class="actions"><form method="post" action="/sair"><button>Sair</button></form></div></section>""")

@app.get("/processos/{cnj}",response_class=HTMLResponse)
def detalhe(cnj:str,request:Request,tab:str="resumo"):
    if not auth(request): return RedirectResponse("/",303)
    if cnj not in (MAIN["cnj"],RELATED["cnj"]):
        return page('<section class="card"><h1>Processo não encontrado</h1><a class="btn" href="/processos">Voltar</a></section>')
    valid={"resumo","movimentacoes","documentos","relacionados","prazos","partes","validacao","historico"}
    if tab not in valid: tab="resumo"
    body=f"""<section class="card"><div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>{TITLE}</h1><div class="chips"><span class="chip">TRABALHISTA</span><span class="chip amber">{MAIN["phase"].upper()}</span><span class="chip">1 PROCESSO VINCULADO</span></div></div><div class="chips"><span class="chip green">v{APP_VERSION}</span><span class="chip">{UPDATE_LABEL}</span></div></div>
{main_nav()}
{tabs(tab)}{tab_content(tab)}
<div class="section"><h2>Controle de integridade</h2><div class="grid"><div class="box"><div class="label">Fonte oficial</div><div class="value">Obrigatória</div></div><div class="box"><div class="label">Correspondência CNJ</div><div class="value">Exata</div></div><div class="box"><div class="label">Documentos</div><div class="value">ID + fonte + captura + hash</div></div><div class="box"><div class="label">Status técnico</div><div class="value">Aguardando validação humana</div></div></div></div>
<div class="actions"><a class="btn" href="/painel">Voltar ao painel principal</a><a class="btn" href="/processos">Ver todos os processos</a><form method="post" action="/sair"><button>Sair</button></form></div></section>"""
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
    VALIDATION["observacoes"]=observacoes.strip().upper()
    now=datetime.now(timezone(timedelta(hours=-3)))
    VALIDATION["validated_at"]=now.strftime("%d/%m/%Y às %H:%M")
    VALIDATION["validated_by"]=AUTHORIZED_EMAIL
    return RedirectResponse(f"/processos/{MAIN['cnj']}?tab=validacao",303)

@app.post("/sair")
def sair():
    r=RedirectResponse("/",303); r.delete_cookie("portically_processos_session"); return r
