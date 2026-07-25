from __future__ import annotations

from .responder import ConversationResponder


class SafeConversationResponder:
    """模型不可用时交回 RAG/通用引导，不伪装成已理解开放式表达。"""

    def __init__(self, primary: ConversationResponder | None):
        self.primary = primary

    def respond(
        self,
        question: str,
        history: list[dict[str, str]],
    ) -> str | None:
        if self.primary is None:
            return None
        try:
            return self.primary.respond(question, history)
        except Exception:
            return None
