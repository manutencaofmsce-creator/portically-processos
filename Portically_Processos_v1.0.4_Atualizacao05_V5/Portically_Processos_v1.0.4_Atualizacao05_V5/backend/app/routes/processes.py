from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.core.auth_security import verify_session_token

router = APIRouter(prefix="/api/processes", tags=["processes"])

PILOT_CNJ = "0800534-37.2025.8.20.5001"


def require_session(request: Request) -> str:
    email = verify_session_token(request.cookies.get(settings.session_cookie_name))
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada.")
    return email


@router.get("/pilot")
def pilot_process(request: Request):
    require_session(request)
    return {
        "cnj": PILOT_CNJ,
        "status": "EM_VALIDACAO",
        "sync_state": "AGUARDANDO_VALIDACAO_HUMANA",
        "official_sync": False,
        "integrity_state": "AGUARDANDO_DOCUMENTOS_OFICIAIS",
        "related_processes_state": "NAO_VALIDADO",
        "source_policy": "SOMENTE_FONTES_OFICIAIS",
        "tabs": [
            "Resumo",
            "Movimentações",
            "Documentos",
            "Fontes Oficiais",
            "Relacionados",
            "Sincronização",
            "Auditoria",
        ],
        "notice": (
            "Nenhuma sincronização oficial foi marcada como concluída. "
            "Dados só devem ser incorporados após coleta verificável e validação humana quando exigida."
        ),
    }
