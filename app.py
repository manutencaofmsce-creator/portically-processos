import os, time, secrets, hashlib, hmac, html, re
from datetime import datetime, timezone, timedelta
import resend
import psycopg
from cryptography.fernet import Fernet
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse

APP_VERSION="1.4.0"
UPDATE_LABEL="Atualização 21 · V21"
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
NEW_CASE_VALIDATION={"metadata":False,"decision":False,"status":False,"next_steps":False,"document_link":False,"observacoes":"","validated_at":"","validated_by":""}

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

NEW_CASE={
 "cnj":"0800534-37.2025.8.20.5001",
 "title":"Maxwell Geroncio de Moura · Procedimento Comum Cível",
 "court":"TJRN",
 "unit":"7ª Vara Cível da Comarca de Natal",
 "class":"Procedimento Comum Cível",
 "claimant":"Maxwell Geroncio de Moura",
 "source":"PJe / TJRN",
 "decision_at":"29/09/2026 16:03:21",
 "judge":"Eduardo André Dantas Silva",
 "decision_id":"202125499",
 "document_id":"26092916032157800000187290537",
 "official_url":"https://pje1g.tjrn.jus.br:443/pje/Processo/ConsultaDocumento/listView.seam?x=26092916032157800000187290537",
 "document_sha256":"461b78eab2e76e3f3bb08c3941ca77d19bd05cae6762fba555328e4cc9776f36",
 "operational_status":"Aguardando comprovação de custas da reconvenção",
 "status_basis":"Classificação operacional baseada exclusivamente na decisão de 29/09/2026; não substitui a situação oficial no PJe.",
 "official_summary":"A prova testemunhal já havia sido deferida para ambas as partes e a decisão de saneamento foi declarada estável.",
 "next_step":"A parte ré/reconvinte deve comprovar, em 15 dias, o recolhimento das custas processuais da reconvenção. Depois do prazo, os autos devem voltar conclusos para decisão.",
 "deadline_note":"O vencimento não foi calculado porque o documento não informa a data de ciência/intimação.",
}

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
.link{{margin-left:8px;padding:12px 0 0 22px;border-left:2px solid #345c80;color:#a8bbce}}.deadline{{border-left:4px solid #ffc857}}.validate-card{{padding:18px;border:1px solid #2b4e6c;border-radius:15px;background:#091827;margin-bottom:12px}}.step{{display:grid;grid-template-columns:42px 1fr auto;gap:14px;align-items:start}}.stepn{{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#173c63;border:1px solid #2f6b9f;font-weight:700}}.checkrow{{display:flex;align-items:center;gap:8px;color:#dce9f5;font-weight:700;white-space:nowrap}}.checkrow input{{width:18px;height:18px;margin:0}}.help{{font-size:13px;color:#8fa7bc;margin-top:6px}}.progress{{height:9px;background:#07111f;border:1px solid #203a54;border-radius:999px;overflow:hidden;margin:10px 0}}.progress i{{display:block;height:100%;background:#2f9b5f}}.status-ok{{color:#9cf0b8}}.status-part{{color:#ffd77b}}.status-pend{{color:#9fb1c4}}textarea{{width:100%;min-height:88px;padding:12px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-family:Arial,sans-serif}}select{{width:100%;padding:14px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-size:16px}}.form-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.radar-row{{display:grid;grid-template-columns:1.2fr .8fr .8fr .7fr auto;gap:12px;align-items:center;padding:14px 0;border-bottom:1px solid #173149}}.radar-row:last-child{{border-bottom:0}}.tiny{{font-size:12px;color:#8fa7bc}}.mask-guide{{margin-top:7px;font-family:monospace;font-size:13px;color:#7fa9ca}}.field-error{{margin-top:7px;font-size:13px;color:#ff9aaa;font-weight:700}}.field-ok{{margin-top:7px;font-size:13px;color:#9cf0b8;font-weight:700}}.input-error{{border-color:#8e3f4d!important}}.input-ok{{border-color:#2e6942!important}}.danger{{background:#5b2430!important}}
button,.btn{{display:inline-block;padding:12px 15px;border:0;border-radius:10px;background:#1f8cff;color:#fff;font-weight:700;text-decoration:none;cursor:pointer}}input{{width:100%;padding:14px;border-radius:10px;border:1px solid #36516d;background:#07111f;color:#fff;font-size:16px}}input[type="text"],input[type="search"],input[type="tel"],textarea{{text-transform:uppercase}}input[type="email"]{{text-transform:lowercase}}label{{display:block;margin:18px 0 8px}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}}.actions form{{margin:0}}.actions form button{{background:#213247}}a{{color:#7fc5ff}}
.badge{{position:fixed;right:14px;bottom:14px;z-index:50;background:#0b1c2d;border:1px solid #315776;border-radius:11px;padding:8px 11px;box-shadow:0 10px 30px #0008;display:flex;align-items:center;gap:7px}}.badge b{{font-size:11px}}.badge span{{font-size:10px;color:#8ec8ff}}.badge small{{display:none}}
@media(max-width:600px){{main{{padding:12px 12px 92px}}.card{{padding:16px}}h1{{font-size:24px}}}}
</style>
<script src="/assets/app.js" defer></script></head><body>
<div class="badge"><b>v{APP_VERSION}</b><span>{UPDATE_LABEL}</span></div>
<main><div class="wrap">{body}</div></main></body></html>""")


APP_JS = r"""
function cpfDigits(v){ return v.replace(/\D/g,"").slice(0,11); }
function cnpjChars(v){ return v.toUpperCase().replace(/[^0-9A-Z]/g,"").slice(0,14); }

function formatCPF(value){
  const n=cpfDigits(value);
  return n.replace(/(\d{3})(\d)/,"$1.$2")
          .replace(/(\d{3})(\d)/,"$1.$2")
          .replace(/(\d{3})(\d{1,2})$/,"$1-$2");
}
function formatCNPJ(value){
  const n=cnpjChars(value);
  return n.replace(/^(.{2})(.)/,"$1.$2")
          .replace(/^(.{2})\.(.{3})(.)/,"$1.$2.$3")
          .replace(/\.(.{3})(.)/,".$1/$2")
          .replace(/(.{4})(.{1,2})$/,"$1-$2");
}
function validCPF(value){
  const n=cpfDigits(value);
  if(n.length!==11 || /^(\d)\1{10}$/.test(n)) return false;
  for(let size=9;size<=10;size++){
    let sum=0;
    for(let i=0;i<size;i++) sum+=Number(n[i])*(size+1-i);
    let d=(sum*10)%11;
    if(d===10) d=0;
    if(d!==Number(n[size])) return false;
  }
  return true;
}
function cnpjValue(ch){ return ch.charCodeAt(0)-48; }
function calcCNPJ(base,weights){
  let sum=0;
  for(let i=0;i<base.length;i++) sum+=cnpjValue(base[i])*weights[i];
  const r=sum%11;
  return String((r===0||r===1)?0:11-r);
}
function validCNPJ(value){
  const n=cnpjChars(value);
  if(!/^[0-9A-Z]{12}[0-9]{2}$/.test(n)) return false;
  if(/^([0-9])\1{13}$/.test(n)) return false;
  const d1=calcCNPJ(n.slice(0,12),[5,4,3,2,9,8,7,6,5,4,3,2]);
  const d2=calcCNPJ(n.slice(0,12)+d1,[6,5,4,3,2,9,8,7,6,5,4,3,2]);
  return n.slice(-2)===d1+d2;
}
function getRadarEls(){
  return {
    tipo:document.getElementById("radar_tipo"),
    doc:document.getElementById("radar_documento"),
    guide:document.getElementById("radar_mask_guide"),
    status:document.getElementById("radar_documento_status")
  };
}
function updateDocumentoMask(clearValue){
  const {tipo,doc,guide,status}=getRadarEls();
  if(!tipo||!doc||!guide||!status) return;
  if(clearValue) doc.value="";
  doc.classList.remove("input-error","input-ok");
  status.className="";
  status.textContent="";
  guide.style.display="block";
  if(tipo.value==="CNPJ"){
    guide.textContent="FORMATO: XX.XXX.XXX/XXXX-XX";
    doc.placeholder="XX.XXX.XXX/XXXX-XX";
    doc.inputMode="text";
    doc.maxLength=18;
    doc.value=formatCNPJ(doc.value);
  }else{
    guide.textContent="FORMATO: XXX.XXX.XXX-XX";
    doc.placeholder="XXX.XXX.XXX-XX";
    doc.inputMode="numeric";
    doc.maxLength=14;
    doc.value=formatCPF(doc.value);
  }
  validateDocumentoField(false);
}
function validateDocumentoField(force){
  const {tipo,doc,guide,status}=getRadarEls();
  if(!tipo||!doc||!guide||!status) return true;
  const raw=tipo.value==="CNPJ"?cnpjChars(doc.value):cpfDigits(doc.value);
  const requiredLength=tipo.value==="CNPJ"?14:11;
  const complete=raw.length===requiredLength;
  doc.classList.remove("input-error","input-ok");
  status.className="";
  status.textContent="";
  guide.style.display=complete?"none":"block";
  if(!complete){
    if(force && raw.length>0){
      status.className="field-error";
      status.textContent=(tipo.value==="CNPJ"?"CNPJ":"CPF")+" INCOMPLETO.";
      doc.classList.add("input-error");
    }
    return false;
  }
  const ok=tipo.value==="CNPJ"?validCNPJ(raw):validCPF(raw);
  if(ok){
    status.className="field-ok";
    status.textContent=(tipo.value==="CNPJ"?"CNPJ":"CPF")+" VÁLIDO.";
    doc.classList.add("input-ok");
    return true;
  }
  status.className="field-error";
  status.textContent=(tipo.value==="CNPJ"?"CNPJ":"CPF")+" INVÁLIDO. CONFIRA OS DÍGITOS INFORMADOS.";
  doc.classList.add("input-error");
  return false;
}
document.addEventListener("change",function(e){
  if(e.target && e.target.id==="radar_tipo") updateDocumentoMask(true);
});
document.addEventListener("blur",function(e){
  if(e.target && e.target.id==="radar_documento") validateDocumentoField(true);
},true);
document.addEventListener("submit",function(e){
  if(e.target && e.target.action && e.target.action.includes("/radar/adicionar")){
    if(!validateDocumentoField(true)){
      e.preventDefault();
      const doc=document.getElementById("radar_documento");
      if(doc) doc.focus();
    }
  }
});
document.addEventListener("input",function(e){
  const el=e.target;
  if(el.id==="radar_documento"){
    const tipo=document.getElementById("radar_tipo");
    el.value=(tipo && tipo.value==="CNPJ")?formatCNPJ(el.value):formatCPF(el.value);
    validateDocumentoField(false);
    return;
  }
  if(el.matches('input[type="email"]')){
    const s=el.selectionStart,t=el.selectionEnd;
    el.value=el.value.toLowerCase();
    try{el.setSelectionRange(s,t)}catch(_){}
    return;
  }
  if(el.matches('input[type="text"],input[type="search"],input[type="tel"],textarea')){
    const s=el.selectionStart,t=el.selectionEnd;
    el.value=el.value.toLocaleUpperCase("pt-BR");
    try{el.setSelectionRange(s,t)}catch(_){}
  }
});
window.addEventListener("pageshow",function(){ updateDocumentoMask(false); });
window.addEventListener("load",function(){ updateDocumentoMask(false); });
"""

@app.get("/assets/app.js", response_class=PlainTextResponse)
def app_js():
    return PlainTextResponse(APP_JS, media_type="application/javascript")

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

def normalize_cnpj(v):
    return "".join(ch for ch in str(v).upper() if ch.isalnum())

def valid_cnpj(v):
    n=normalize_cnpj(v)
    if len(n)!=14 or not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}",n):
        return False
    if n.isdigit() and n==n[0]*14:
        return False
    def char_value(ch):
        return ord(ch)-48
    def calc(base,weights):
        s=sum(char_value(a)*b for a,b in zip(base,weights))
        r=s%11
        return "0" if r in (0,1) else str(11-r)
    d1=calc(n[:12],[5,4,3,2,9,8,7,6,5,4,3,2])
    d2=calc(n[:12]+d1,[6,5,4,3,2,9,8,7,6,5,4,3,2])
    return n[-2:]==d1+d2

def normalize_document(kind,value):
    return only_digits(value) if kind=="CPF" else normalize_cnpj(value)

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
    if kind=="CPF":
        n=only_digits(value)
        if len(n)==11: return f"{n[:3]}.***.***-{n[-2:]}"
    if kind=="CNPJ":
        n=normalize_cnpj(value)
        if len(n)==14: return f"{n[:2]}.***.***/****-{n[-2:]}"
    return "Documento inválido"

def db_ready():
    return bool(DATABASE_URL and DATA_ENCRYPTION_KEY and DATA_HMAC_KEY)

def database_status():
    if not db_ready():
        return False, "not-linked"
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.execute("SELECT to_regclass('public.radar_items')")
                table=cur.fetchone()[0]
        return bool(table), "connected" if table else "table-missing"
    except Exception as e:
        print(f"DB_HEALTH_ERROR: {type(e).__name__}", flush=True)
        return False, "connection-error"

def db_conn():
    return psycopg.connect(DATABASE_URL, autocommit=True)

def crypto_box():
    key=DATA_ENCRYPTION_KEY.strip()
    key += "=" * ((4 - len(key) % 4) % 4)
    return Fernet(key.encode())

def doc_fingerprint(kind,value):
    return hmac.new(DATA_HMAC_KEY.encode(),normalize_document(kind,value).encode(),hashlib.sha256).hexdigest()

def encrypt_doc(kind,value):
    return crypto_box().encrypt(normalize_document(kind,value).encode()).decode()

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
            cur.execute("""CREATE TABLE IF NOT EXISTS process_records(
                cnj TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                court TEXT NOT NULL,
                unit_name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                claimant TEXT,
                source TEXT NOT NULL,
                operational_status TEXT NOT NULL,
                status_basis TEXT NOT NULL,
                official_summary TEXT NOT NULL,
                latest_decision_at TEXT NOT NULL,
                judge_name TEXT NOT NULL,
                next_step TEXT NOT NULL,
                deadline_note TEXT NOT NULL,
                human_validation_status TEXT NOT NULL DEFAULT 'Aguardando validação humana',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
            cur.execute("""CREATE TABLE IF NOT EXISTS process_documents(
                id TEXT PRIMARY KEY,
                process_cnj TEXT NOT NULL,
                decision_id TEXT,
                document_type TEXT NOT NULL,
                document_at TEXT NOT NULL,
                signer TEXT NOT NULL,
                source TEXT NOT NULL,
                official_url TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                capture_status TEXT NOT NULL,
                storage_status TEXT NOT NULL,
                validation_status TEXT NOT NULL DEFAULT 'Aguardando validação humana',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
            cur.execute("""CREATE TABLE IF NOT EXISTS process_validations(
                process_cnj TEXT PRIMARY KEY,
                metadata_ok BOOLEAN NOT NULL DEFAULT FALSE,
                decision_ok BOOLEAN NOT NULL DEFAULT FALSE,
                status_ok BOOLEAN NOT NULL DEFAULT FALSE,
                next_steps_ok BOOLEAN NOT NULL DEFAULT FALSE,
                document_link_ok BOOLEAN NOT NULL DEFAULT FALSE,
                notes TEXT NOT NULL DEFAULT '',
                validated_at TIMESTAMPTZ,
                validated_by TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
            cur.execute("""INSERT INTO process_records(
                cnj,title,court,unit_name,class_name,claimant,source,operational_status,
                status_basis,official_summary,latest_decision_at,judge_name,next_step,deadline_note
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (cnj) DO UPDATE SET
                title=EXCLUDED.title,court=EXCLUDED.court,unit_name=EXCLUDED.unit_name,
                class_name=EXCLUDED.class_name,claimant=EXCLUDED.claimant,source=EXCLUDED.source,
                operational_status=EXCLUDED.operational_status,status_basis=EXCLUDED.status_basis,
                official_summary=EXCLUDED.official_summary,latest_decision_at=EXCLUDED.latest_decision_at,
                judge_name=EXCLUDED.judge_name,next_step=EXCLUDED.next_step,
                deadline_note=EXCLUDED.deadline_note,updated_at=NOW()""",
                (NEW_CASE["cnj"],NEW_CASE["title"],NEW_CASE["court"],NEW_CASE["unit"],
                 NEW_CASE["class"],NEW_CASE["claimant"],NEW_CASE["source"],
                 NEW_CASE["operational_status"],NEW_CASE["status_basis"],NEW_CASE["official_summary"],
                 NEW_CASE["decision_at"],NEW_CASE["judge"],NEW_CASE["next_step"],NEW_CASE["deadline_note"]))
            cur.execute("""INSERT INTO process_documents(
                id,process_cnj,decision_id,document_type,document_at,signer,source,
                official_url,sha256,capture_status,storage_status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                process_cnj=EXCLUDED.process_cnj,decision_id=EXCLUDED.decision_id,
                document_type=EXCLUDED.document_type,document_at=EXCLUDED.document_at,
                signer=EXCLUDED.signer,source=EXCLUDED.source,official_url=EXCLUDED.official_url,
                sha256=EXCLUDED.sha256,capture_status=EXCLUDED.capture_status,
                storage_status=EXCLUDED.storage_status,updated_at=NOW()""",
                (NEW_CASE["document_id"],NEW_CASE["cnj"],NEW_CASE["decision_id"],"Decisão",
                 NEW_CASE["decision_at"],NEW_CASE["judge"],NEW_CASE["source"],
                 NEW_CASE["official_url"],NEW_CASE["document_sha256"],
                 "PDF fornecido pelo usuário; data de captura não informada no documento",
                 "Metadados, vínculo e hash registrados; arquivo não publicado no repositório público"))
            cur.execute("""INSERT INTO process_validations(process_cnj)
                           VALUES (%s) ON CONFLICT (process_cnj) DO NOTHING""",(NEW_CASE["cnj"],))

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

def load_new_case_validation():
    state=NEW_CASE_VALIDATION.copy()
    if not db_ready():
        return state
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT metadata_ok,decision_ok,status_ok,next_steps_ok,document_link_ok,
                                      notes,validated_at,validated_by
                               FROM process_validations WHERE process_cnj=%s""",(NEW_CASE["cnj"],))
                row=cur.fetchone()
        if row:
            state.update({"metadata":row[0],"decision":row[1],"status":row[2],
                          "next_steps":row[3],"document_link":row[4],"observacoes":row[5] or "",
                          "validated_at":row[6].astimezone(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y às %H:%M") if row[6] else "",
                          "validated_by":row[7] or ""})
    except Exception as e:
        print(f"PROCESS_VALIDATION_READ_ERROR: {type(e).__name__}", flush=True)
    return state

def new_case_validation_status(state=None):
    state=state or load_new_case_validation()
    done=sum(1 for key in ("metadata","decision","status","next_steps","document_link") if state.get(key))
    if done==5: return "Validado manualmente",done,"status-ok"
    if done>0: return "Parcialmente validado",done,"status-part"
    return "Aguardando validação humana",done,"status-pend"

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
    ok,_=database_status()
    radar_count=0
    if ok:
        try:
            with db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM radar_items")
                    radar_count=int(cur.fetchone()[0])
        except Exception as e:
            print(f"RADAR_COUNT_ERROR: {type(e).__name__}", flush=True)
    pending_validations=(1 if validation_status()[1] < 6 else 0)+(1 if new_case_validation_status()[1] < 5 else 0)
    return {"processos":2,"cpf_cnpj":radar_count,"movimentacoes":0,"novos_processos":0,"alertas":0,"validacoes":pending_validations}

def tabs(active,cnj=None):
    target=cnj or MAIN["cnj"]
    items=[("resumo","Resumo"),("movimentacoes","Movimentações"),("documentos","Documentos"),
           ("relacionados","Processos relacionados"),("prazos","Prazos"),("partes","Partes"),("validacao","Validação"),("historico","Histórico")]
    return '<div class="tabs">'+''.join(
      f'<a class="tab {"active" if k==active else ""}" href="/processos/{target}?tab={k}">{label}</a>'
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

def new_case_validation_html():
    state=load_new_case_validation()
    status,done,css=new_case_validation_status(state)
    pct=int(done/5*100)
    checked=lambda key: "checked" if state.get(key) else ""
    persistence="PostgreSQL" if db_ready() else "memória temporária (banco não configurado)"
    return f"""<div class="notice"><b>Validação humana obrigatória:</b> marque apenas os itens conferidos diretamente no PJe/TJRN e no PDF oficial. A classificação operacional do sistema não substitui o andamento oficial.</div>
<div class="proc"><div class="top"><div><h2>Validação da ficha e do documento</h2><p class="{css}"><b>{status}</b> · {done} de 5 itens confirmados</p></div><div class="version-inline">{pct}% concluído</div></div>
<div class="progress"><i style="width:{pct}%"></i></div>
<form method="post" action="/processos/{NEW_CASE["cnj"]}/validar">
<div class="validate-card"><div class="step"><div class="stepn">1</div><div><h3>Metadados oficiais</h3><p><span class="cnj">{NEW_CASE["cnj"]}</span> · {NEW_CASE["class"]} · {NEW_CASE["unit"]}</p><div class="help">Confira número CNJ, classe, unidade e requerente no cadastro oficial.</div></div><label class="checkrow"><input type="checkbox" name="metadata" {checked("metadata")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">2</div><div><h3>Decisão de 29/09/2026</h3><p>Documento {NEW_CASE["document_id"]}, assinado por {NEW_CASE["judge"]} às 16:03:21.</p><div class="help">Compare data, assinatura, número da decisão e conteúdo essencial com o PDF.</div></div><label class="checkrow"><input type="checkbox" name="decision" {checked("decision")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">3</div><div><h3>Status operacional</h3><p>{NEW_CASE["operational_status"]}</p><div class="help">Esta é uma classificação interna baseada na decisão, não um andamento oficial autônomo.</div></div><label class="checkrow"><input type="checkbox" name="status" {checked("status")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">4</div><div><h3>Próximos passos</h3><p>{NEW_CASE["next_step"]}</p><div class="help">Não confirme vencimento: a data de ciência/intimação não consta no documento.</div></div><label class="checkrow"><input type="checkbox" name="next_steps" {checked("next_steps")}> Confirmado</label></div></div>
<div class="validate-card"><div class="step"><div class="stepn">5</div><div><h3>Vínculo documental</h3><p>ID {NEW_CASE["document_id"]} · SHA-256 <span class="cnj">{NEW_CASE["document_sha256"]}</span></p><div class="help">Abra a fonte oficial e confirme que o documento corresponde a este processo e a este hash.</div></div><label class="checkrow"><input type="checkbox" name="document_link" {checked("document_link")}> Confirmado</label></div></div>
<label>Observações da validação</label><textarea name="observacoes" placeholder="Registre a fonte consultada e qualquer divergência encontrada.">{esc(state.get("observacoes",""))}</textarea>
<div class="actions"><button type="submit">Salvar validação</button><a class="btn" href="{esc(NEW_CASE["official_url"])}" target="_blank" rel="noopener noreferrer">Abrir documento no PJe</a></div>
</form></div>
<div class="section"><h2>Registro da validação</h2><div class="grid"><div class="box"><div class="label">Status</div><div class="value {css}">{status}</div></div><div class="box"><div class="label">Última validação</div><div class="value">{esc(state.get("validated_at") or "Ainda não realizada")}</div></div><div class="box"><div class="label">Usuário</div><div class="value">{esc(state.get("validated_by") or "—")}</div></div><div class="box"><div class="label">Persistência</div><div class="value">{persistence}</div></div></div></div>"""

def new_case_tab_content(tab):
    state=load_new_case_validation()
    status,done,css=new_case_validation_status(state)
    if tab=="validacao":
        return new_case_validation_html()
    if tab=="movimentacoes":
        return f"""<div class="notice">A cronologia abaixo contém somente fatos presentes na decisão enviada. A movimentação completa depende de consulta ao PJe.</div>
<div class="timeline"><div class="event"><h3>Decisão de saneamento anterior</h3><p>A decisão Num. 171200069 havia deferido prova testemunhal para ambas as partes, na ação principal e na reconvenção.</p><span class="chip amber">Referida na decisão enviada</span></div>
<div class="event"><h3>Decisão de 29/09/2026</h3><p>A decisão de saneamento foi declarada estável. A parte ré/reconvinte foi intimada, por seu advogado, a comprovar em 15 dias o recolhimento das custas da reconvenção.</p><span class="chip">Documento {NEW_CASE["document_id"]}</span></div>
<div class="event"><h3>Próximo ato previsto</h3><p>Depois do prazo, os autos devem voltar conclusos para decisão.</p><span class="chip amber">Ainda não confirmado no PJe</span></div></div>"""
    if tab=="documentos":
        return f"""<div class="notice">O PDF fornecido foi usado somente para registrar os dados abaixo. Ele não foi adicionado ao repositório público. A correspondência com a fonte oficial continua pendente de validação humana.</div>
<div class="proc"><div class="top"><div><span class="chip">DECISÃO</span><h3 style="margin-top:10px">Decisão sobre prova e custas da reconvenção</h3><p>Processo: <span class="cnj">{NEW_CASE["cnj"]}</span> · {NEW_CASE["source"]}</p></div><span class="chip amber">{status.upper()}</span></div>
<div class="grid"><div class="box"><div class="label">ID oficial</div><div class="value cnj">{NEW_CASE["document_id"]}</div></div><div class="box"><div class="label">Decisão</div><div class="value">Num. {NEW_CASE["decision_id"]}</div></div><div class="box"><div class="label">Data e assinatura</div><div class="value">{NEW_CASE["decision_at"]}</div><p>{NEW_CASE["judge"]}</p></div><div class="box"><div class="label">Fonte</div><div class="value">{NEW_CASE["source"]}</div></div></div>
<div class="section"><div class="box"><div class="label">SHA-256 do PDF recebido</div><div class="value cnj">{NEW_CASE["document_sha256"]}</div><p>Data de captura: não informada no documento. Metadados e hash registrados; arquivo não publicado no repositório.</p></div></div>
<div class="actions"><a class="btn" href="{esc(NEW_CASE["official_url"])}" target="_blank" rel="noopener noreferrer">Consultar documento oficial</a><a class="btn" href="/processos/{NEW_CASE["cnj"]}?tab=validacao">Validar vínculo documental</a></div></div>"""
    if tab=="relacionados":
        return """<div class="empty">Nenhum processo relacionado foi identificado no documento enviado. Não foram inferidos vínculos ausentes.</div>"""
    if tab=="prazos":
        return f"""<div class="notice">{NEW_CASE["deadline_note"]}</div><div class="box deadline"><div class="label">Providência determinada</div><div class="value">15 dias</div><p>Comprovar o recolhimento das custas processuais referentes à reconvenção.</p><span class="chip amber">Termo inicial e vencimento não informados no documento</span></div>"""
    if tab=="partes":
        return f"""<div class="grid"><div class="box"><div class="label">Requerente</div><div class="value">{NEW_CASE["claimant"]}</div></div><div class="box"><div class="label">Parte ré/reconvinte</div><div class="value">Nome não informado no documento enviado</div></div></div>"""
    if tab=="historico":
        return f"""<div class="grid"><div class="box"><span class="chip green">ATUAL</span><div class="label" style="margin-top:8px">Versão</div><div class="value">v{APP_VERSION} · {UPDATE_LABEL}</div><p>Inclusão persistente do processo, decisão, próximos passos, vínculo documental e validação humana.</p></div><div class="box"><div class="label">Origem da inclusão</div><div class="value">PDF fornecido pelo usuário</div><p>Somente dados presentes no documento foram cadastrados.</p></div></div>"""
    return f"""<div class="notice"><b>Leitura rápida:</b> a decisão de 29/09/2026 manteve estável o saneamento e determinou que a parte ré/reconvinte comprovasse o recolhimento das custas da reconvenção antes da continuidade da produção de provas.</div>
<div class="grid"><div class="box"><div class="label">Processo</div><div class="value cnj">{NEW_CASE["cnj"]}</div></div><div class="box"><div class="label">Classe</div><div class="value">{NEW_CASE["class"]}</div></div><div class="box"><div class="label">Unidade</div><div class="value">{NEW_CASE["court"]}</div><p>{NEW_CASE["unit"]}</p></div><div class="box"><div class="label">Status operacional</div><div class="value">{NEW_CASE["operational_status"]}</div><p>{NEW_CASE["status_basis"]}</p></div><div class="box"><div class="label">Validação</div><div class="value {css}">{status}</div><p>{done} de 5 itens confirmados</p><a class="btn" href="/processos/{NEW_CASE["cnj"]}?tab=validacao">Revisar ficha</a></div></div>
<div class="section"><h2>Decisão mais recente no documento</h2><div class="proc"><h3>{NEW_CASE["decision_at"]} · {NEW_CASE["judge"]}</h3><p>{NEW_CASE["official_summary"]}</p><p><b>Próximo passo:</b> {NEW_CASE["next_step"]}</p><span class="chip amber">{NEW_CASE["deadline_note"]}</span></div></div>"""

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
<div class="box"><div class="label">Versão anterior</div><div class="value">v1.2.9 · Atualização 19 · V19</div><p>Agrupamento do caso e vínculo entre processo principal e carta precatória.</p></div></div>"""
    return f"""<div class="notice"><b>Leitura rápida:</b> Processo em fase de execução. Há uma carta precatória vinculada no TRT-21, em Natal/RN, destinada ao cumprimento de citação originada no processo principal de Fortaleza/CE.</div>
<div class="grid"><div class="box"><div class="label">Processo principal</div><div class="value cnj">{MAIN["cnj"]}</div></div><div class="box"><div class="label">Tribunal</div><div class="value">{MAIN["court"]}</div><p>{MAIN["unit"]}</p></div><div class="box"><div class="label">Fase</div><div class="value">{MAIN["phase"]}</div></div><div class="box"><div class="label">Sincronização</div><div class="value">{validation_status()[0]}</div><p>{validation_status()[1]} de 6 itens confirmados</p><a class="btn" href="/processos/{MAIN["cnj"]}?tab=validacao">Iniciar validação</a></div></div>
<div class="section"><h2>Entenda este processo</h2><div class="grid"><div class="box"><h3>Execução</h3><p>Fase em que o Judiciário busca o cumprimento da obrigação ou pagamento indicado no processo.</p></div><div class="box"><h3>Por que há um processo em Natal?</h3><p>O processo principal tramita em Fortaleza/CE. A carta precatória foi aberta no TRT-21 para cumprir uma diligência em Natal/RN.</p></div><div class="box"><h3>Carta Precatória</h3><p>É o instrumento usado para pedir a outro juízo que cumpra uma diligência fora da área do processo principal.</p></div></div></div>"""

@app.get("/health")
def health():
    ok,dbstate=database_status()
    radar_count=None
    if ok:
        try:
            with db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM radar_items")
                    radar_count=int(cur.fetchone()[0])
        except Exception as e:
            print(f"HEALTH_COUNT_ERROR: {type(e).__name__}", flush=True)
    return {"status":"ok","service":"portically-processos","version":APP_VERSION,"update":UPDATE_LABEL,"database":dbstate,"radar_items":radar_count}

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
<div class="section"><h2>Resumo atual</h2><div class="grid"><div class="box"><div class="label">Processos em acompanhamento</div><div class="value">2 fichas cadastradas</div><p class="cnj">{MAIN["cnj"]}</p><p class="cnj">{NEW_CASE["cnj"]}</p></div><div class="box"><div class="label">Status da validação do caso trabalhista</div><div class="value {css}">{status}</div><p>{done} de 6 itens confirmados</p></div><div class="box"><div class="label">Novo processo cível</div><div class="value">{new_case_validation_status()[0]}</div><p>{NEW_CASE["operational_status"]}</p></div><div class="box"><div class="label">Radar processual</div><div class="value">Ainda não configurado</div><p>Cadastre CPF/CNPJ para preparar a busca de novos processos nas fontes compatíveis.</p></div></div></div>
<div class="actions"><form method="post" action="/sair"><button>Sair</button></form></div></section>"""
    return page(body,"Painel · Portically Processos")

@app.get("/radar",response_class=HTMLResponse)
def radar(request:Request,msg:str=""):
    if not auth(request): return RedirectResponse("/",303)
    db_ok,db_state=database_status()
    items=list_radar_items() if db_ok else []
    rows=""
    for item in items:
        rows+=f"""<div class="radar-row"><div><div class="value">{esc(item["nome"])}</div><div class="tiny">{item["tipo"]} · {esc(item["mascara"])}</div></div><div><div class="label">Frequência</div><div>{esc(item["frequencia"])}</div></div><div><div class="label">Alertas</div><div>{esc(item["canais"])}</div><div class="tiny">E-mail: {esc(item["email"])}</div><div class="tiny">WhatsApp: {esc(item["whatsapp"])}</div></div><div><span class="chip amber">{esc(item["status"])}</span></div><form method="post" action="/radar/{item["id"]}/excluir"><button class="danger" type="submit">Excluir</button></form></div>"""
    if not rows:
        rows='<div class="empty">Nenhum CPF ou CNPJ cadastrado.</div>'
    notice=f'<div class="notice">{esc(msg)}</div>' if msg else ''
    body=f"""<section class="card">{app_header("Radar Processual","Cadastre CPF/CNPJ para acompanhar possíveis novos processos e alertas nas fontes compatíveis.")}
{notice}
{'' if db_ok else '<div class="notice"><b>Banco seguro indisponível.</b> Estado: '+esc(db_state)+'. O cadastro fica bloqueado até a conexão ser restabelecida.</div>'}
<div class="notice"><b>Como funciona:</b> o cadastro abaixo cria o alvo de monitoramento. A busca automática nas fontes oficiais será ativada conforme cada fonte permitir pesquisa por CPF/CNPJ. CAPTCHA, login e restrições não serão contornados.</div>
<div class="proc"><h2>Novo monitoramento</h2>
<form method="post" action="/radar/adicionar"><div class="form-grid">
<div><label>Tipo</label><select name="tipo" id="radar_tipo" required><option>CPF</option><option>CNPJ</option></select></div>
<div><label>Nome / Razão social</label><input name="nome" required placeholder="Identificação do titular"></div>
<div><label>CPF/CNPJ</label><input name="documento" id="radar_documento" required inputmode="numeric" maxlength="14" placeholder="XXX.XXX.XXX-XX" autocomplete="off"><div class="mask-guide" id="radar_mask_guide">FORMATO: XXX.XXX.XXX-XX</div><div id="radar_documento_status"></div></div>
<div><label>Frequência</label><select name="frequencia"><option>Diária</option><option>Semanal</option><option>Manual</option></select></div>
</div>
<div class="form-grid">
<div><label><input type="checkbox" name="email_alerta" value="1" style="width:auto"> Avisar por e-mail</label><input type="email" name="email_alerta_endereco" autocomplete="email" placeholder="exemplo@dominio.com"><div class="tiny">Informe o e-mail que receberá os alertas.</div></div>
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
    numero=normalize_document(tipo,documento)
    ok=(tipo=="CPF" and valid_cpf(numero)) or (tipo=="CNPJ" and valid_cnpj(numero))
    if not ok:
        return RedirectResponse("/radar?msg=CPF/CNPJ inválido. Confira os números e tente novamente.",303)
    if email_alerta and not valid_email(email_alerta_endereco):
        return RedirectResponse("/radar?msg=Informe um e-mail válido para ativar os alertas por e-mail.",303)
    if whatsapp_alerta and not valid_whatsapp(whatsapp_numero):
        return RedirectResponse("/radar?msg=Informe um número de WhatsApp válido para ativar os alertas.",303)
    db_ok,db_state=database_status()
    if not db_ok:
        return RedirectResponse(f"/radar?msg=Banco seguro indisponível ({db_state}). O cadastro não foi gravado.",303)
    item_id=secrets.token_hex(8)
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO radar_items(id,tipo,nome,doc_cipher,doc_hash,mascara,frequencia,email_alerta,whatsapp_alerta,status,whatsapp_cipher,whatsapp_mask,email_cipher,email_mask)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (item_id,tipo,nome,encrypt_doc(tipo,numero),doc_fingerprint(tipo,numero),mask_doc(tipo,numero),frequencia,
                             bool(email_alerta),bool(whatsapp_alerta),"Aguardando integração",
                             encrypt_value(normalize_whatsapp(whatsapp_numero)) if whatsapp_alerta else None,
                             mask_whatsapp(whatsapp_numero) if whatsapp_alerta else None,
                             encrypt_value(email_alerta_endereco) if email_alerta else None,
                             mask_email(email_alerta_endereco) if email_alerta else None))
        audit("CREATE","radar_item",item_id,f"{tipo} {mask_doc(tipo,numero)}")
    except Exception as e:
        print(f"RADAR_CREATE_ERROR: {type(e).__name__}", flush=True)
        return RedirectResponse("/radar?msg=Falha ao gravar o monitoramento. O erro foi registrado para diagnóstico.",303)
    print(f"RADAR_CREATE_OK: {item_id}", flush=True)
    return RedirectResponse("/radar?msg=Monitoramento cadastrado e gravado com sucesso.",303)

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
<div class="proc"><div class="chips"><span class="chip">JUSTIÇA DO TRABALHO</span><span class="chip amber">{MAIN["phase"].upper()}</span><span class="chip">1 VÍNCULO</span></div><h2 class="case-title">{TITLE}</h2><div class="cnj">{MAIN["cnj"]}</div><div class="case-footer"><div><div class="label">ORIGEM</div><p class="case-location">{MAIN["court"]} · {MAIN["unit"]}</p></div><a class="btn" href="/processos/{MAIN["cnj"]}?tab=resumo">Ver detalhes do caso</a></div></div>
<div class="proc section"><div class="chips"><span class="chip">JUSTIÇA ESTADUAL</span><span class="chip amber">{NEW_CASE["operational_status"].upper()}</span><span class="chip">VALIDAÇÃO HUMANA</span></div><h2 class="case-title">{NEW_CASE["title"]}</h2><div class="cnj">{NEW_CASE["cnj"]}</div><div class="case-footer"><div><div class="label">ORIGEM</div><p class="case-location">{NEW_CASE["court"]} · {NEW_CASE["unit"]}</p></div><a class="btn" href="/processos/{NEW_CASE["cnj"]}?tab=resumo">Ver detalhes do caso</a></div></div>
<div class="actions"><form method="post" action="/sair"><button>Sair</button></form></div></section>""")

@app.get("/processos/{cnj}",response_class=HTMLResponse)
def detalhe(cnj:str,request:Request,tab:str="resumo"):
    if not auth(request): return RedirectResponse("/",303)
    if cnj not in (MAIN["cnj"],RELATED["cnj"],NEW_CASE["cnj"]):
        return page('<section class="card"><h1>Processo não encontrado</h1><a class="btn" href="/processos">Voltar</a></section>')
    valid={"resumo","movimentacoes","documentos","relacionados","prazos","partes","validacao","historico"}
    if tab not in valid: tab="resumo"
    if cnj==NEW_CASE["cnj"]:
        validation_label=new_case_validation_status()[0]
        body=f"""<section class="card"><div class="top"><div><div class="brand">PORTICALLY HUB · PROCESSOS</div><h1>{NEW_CASE["title"]}</h1><div class="chips"><span class="chip">CÍVEL</span><span class="chip amber">{NEW_CASE["operational_status"].upper()}</span><span class="chip">{validation_label.upper()}</span></div></div><div class="chips"><span class="chip green">v{APP_VERSION}</span><span class="chip">{UPDATE_LABEL}</span></div></div>
{main_nav()}
{tabs(tab,NEW_CASE["cnj"])}{new_case_tab_content(tab)}
<div class="section"><h2>Controle de integridade</h2><div class="grid"><div class="box"><div class="label">Fonte</div><div class="value">{NEW_CASE["source"]}</div></div><div class="box"><div class="label">Correspondência CNJ</div><div class="value">Exata no PDF recebido</div></div><div class="box"><div class="label">Documento</div><div class="value">ID oficial + link + SHA-256</div></div><div class="box"><div class="label">Status técnico</div><div class="value">{validation_label}</div></div></div></div>
<div class="actions"><a class="btn" href="/painel">Voltar ao painel principal</a><a class="btn" href="/processos">Ver todos os processos</a><form method="post" action="/sair"><button>Sair</button></form></div></section>"""
        return page(body,f"Processo {NEW_CASE['cnj']}")
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
    data_ciencia:str=Form(""),observacoes:str=Form(""),
    metadata:str=Form(None),decision:str=Form(None),status_ok:str=Form(None,alias="status"),
    next_steps:str=Form(None),document_link:str=Form(None)):
    if not auth(request): return RedirectResponse("/",303)
    if cnj==NEW_CASE["cnj"]:
        now=datetime.now(timezone.utc)
        state={"metadata":bool(metadata),"decision":bool(decision),"status":bool(status_ok),
               "next_steps":bool(next_steps),"document_link":bool(document_link),
               "observacoes":observacoes.strip().upper(),"validated_at":now.astimezone(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y às %H:%M"),
               "validated_by":AUTHORIZED_EMAIL}
        NEW_CASE_VALIDATION.update(state)
        if db_ready():
            with db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO process_validations(
                        process_cnj,metadata_ok,decision_ok,status_ok,next_steps_ok,document_link_ok,
                        notes,validated_at,validated_by,updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (process_cnj) DO UPDATE SET
                        metadata_ok=EXCLUDED.metadata_ok,decision_ok=EXCLUDED.decision_ok,
                        status_ok=EXCLUDED.status_ok,next_steps_ok=EXCLUDED.next_steps_ok,
                        document_link_ok=EXCLUDED.document_link_ok,notes=EXCLUDED.notes,
                        validated_at=EXCLUDED.validated_at,validated_by=EXCLUDED.validated_by,updated_at=NOW()""",
                        (cnj,state["metadata"],state["decision"],state["status"],state["next_steps"],
                         state["document_link"],state["observacoes"],now,AUTHORIZED_EMAIL))
                    final_status=new_case_validation_status(state)[0]
                    cur.execute("UPDATE process_records SET human_validation_status=%s,updated_at=NOW() WHERE cnj=%s",
                                (final_status,cnj))
                    cur.execute("UPDATE process_documents SET validation_status=%s,updated_at=NOW() WHERE process_cnj=%s",
                                ("Vínculo validado manualmente" if state["document_link"] else "Aguardando validação humana",cnj))
            audit("VALIDATE","process",cnj,f"{new_case_validation_status(state)[1]}/5 itens confirmados")
        return RedirectResponse(f"/processos/{cnj}?tab=validacao",303)
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
