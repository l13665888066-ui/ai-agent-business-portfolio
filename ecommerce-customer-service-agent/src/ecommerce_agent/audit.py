from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from time import time
from typing import Any


SENSITIVE_KEYS = {"token", "authorization", "api_key", "secret"}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("***" if key.lower() in SENSITIVE_KEYS else _scrub(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


class AuditLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = RLock()

    def write(self, event: dict[str, Any]) -> None:
        record = {"timestamp": time(), **_scrub(event)}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")


class NullAuditLogger:
    def write(self, event: dict[str, Any]) -> None:
        return None
