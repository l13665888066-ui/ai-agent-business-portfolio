from __future__ import annotations

import re
from typing import Any


class CustomerFriendlyKnowledgeService:
    """保留检索证据，移除只供内部使用的知识库字段。"""

    INTERNAL_PREFIX = "根据店铺规则："

    def __init__(self, knowledge_service: Any):
        self.knowledge_service = knowledge_service

    def answer(self, question: str) -> dict[str, Any]:
        result = dict(self.knowledge_service.answer(question))
        if not result.get("matched"):
            return result

        raw_answer = str(result.get("answer", "")).strip()
        rule = self._extract_rule_content(raw_answer)
        if rule:
            result["answer"] = rule
        return result

    @classmethod
    def _extract_rule_content(cls, answer: str) -> str:
        text = answer.removeprefix(cls.INTERNAL_PREFIX).strip()
        match = re.search(
            r"规则内容：(.*?)(?:\n限制条件：|\n客服回复边界：|$)",
            text,
            flags=re.DOTALL,
        )
        if match:
            return " ".join(match.group(1).split())

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
            and not line.startswith(("适用问题：", "客服回复边界：", "限制条件："))
        ]
        return " ".join(lines).strip()
