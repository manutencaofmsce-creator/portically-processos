from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import settings

_LOCK = Lock()


def audit_event(event: str, result: str, **details: Any) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "result": result,
        **details,
    }
    path = Path(settings.audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
