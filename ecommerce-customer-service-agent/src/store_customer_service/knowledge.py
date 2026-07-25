from __future__ import annotations

from typing import Any


class ResilientKnowledgeService:
    """向量检索异常时降级到本地知识检索，避免整段客服流程失败。"""

    def __init__(self, primary: Any, fallback: Any):
        self.primary = primary
        self.fallback = fallback

    def answer(self, question: str) -> dict[str, Any]:
        try:
            return self.primary.answer(question)
        except Exception as error:
            result = self.fallback.answer(question)
            result = dict(result)
            result["degraded"] = True
            result["degraded_reason"] = type(error).__name__
            return result
