from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from time import time
from typing import Any


@dataclass
class PendingAction:
    tool_name: str
    missing_params: list[str]
    collected_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    pending: PendingAction | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    updated_at: float = field(default_factory=time)


class InMemoryConversationStore:
    """按 session 隔离上下文，避免不同用户之间串单。"""

    def __init__(self, max_history: int = 12):
        self._states: dict[str, ConversationState] = {}
        self._lock = RLock()
        self.max_history = max_history

    def get(self, session_id: str) -> ConversationState:
        with self._lock:
            return self._states.setdefault(session_id, ConversationState())

    def set_pending(
        self,
        session_id: str,
        tool_name: str,
        missing_params: list[str],
        collected_args: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            state = self.get(session_id)
            state.pending = PendingAction(
                tool_name=tool_name,
                missing_params=list(missing_params),
                collected_args=dict(collected_args or {}),
            )
            state.updated_at = time()

    def clear_pending(self, session_id: str) -> None:
        with self._lock:
            state = self.get(session_id)
            state.pending = None
            state.updated_at = time()

    def append(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            state = self.get(session_id)
            state.history.append({"role": role, "content": content})
            state.history = state.history[-self.max_history :]
            state.updated_at = time()
