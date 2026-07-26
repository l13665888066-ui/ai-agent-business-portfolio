from __future__ import annotations

import json
from datetime import date
from typing import Any

from .models import ExpenseApplication, SemanticReview


class LocalPurposeReviewer:
    """外部模型不可用时保守提示，不参与金额或审批结论。"""

    def review(
        self,
        application: ExpenseApplication,
    ) -> SemanticReview:
        suggestions = []
        if len(application.purpose) < 16:
            suggestions.append(
                "建议补充业务对象、地点或费用与工作的关联"
            )
        if not application.attachment_id:
            suggestions.append(
                "当前未上传票据附件，正式报销仍需补充原始票据"
            )
        return SemanticReview(
            mode="rule_fallback",
            summary="用途说明已完成基础结构检查",
            risk_hints=[],
            suggestions=suggestions,
        )


class LLMPurposeReviewer:
    """模型只检查材料表达，输出还要经过系统事实一致性校验。"""

    SYSTEM_PROMPT = """你是企业费用报销材料审核助手。
只评估用途说明是否清楚，以及还需要申请人补充哪些事实。
系统传入的费用类型、金额、发生日期和用途说明均为已填写事实，不得把非空字段说成缺失或未知。
当前日期会单独提供；只有发生日期晚于当前日期时，才可以提示“未来日期”。
不得判断报销是否批准，不得修改金额、员工、预算或发票事实。
请只返回JSON对象：
{
  "summary": "一句话材料摘要",
  "risk_hints": ["最多3条事实风险提示"],
  "suggestions": ["最多3条补充建议"]
}
信息不足时只指出确实缺少的事实，不得编造。"""

    CONTRADICTION_WORDS = (
        "缺失",
        "未知",
        "未填写",
        "没有填写",
        "完全未知",
    )

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
    ):
        from langchain_openai import ChatOpenAI

        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0,
            timeout=10,
            max_retries=0,
        ).bind(response_format={"type": "json_object"})

    @classmethod
    def _is_fact_consistent(
        cls,
        text: str,
        application: ExpenseApplication,
    ) -> bool:
        if (
            application.expense_type
            and "费用类型" in text
            and any(word in text for word in cls.CONTRADICTION_WORDS)
        ):
            return False
        if (
            application.purpose
            and "用途" in text
            and any(word in text for word in cls.CONTRADICTION_WORDS)
        ):
            return False
        if application.expense_date and "未来" in text:
            try:
                if date.fromisoformat(application.expense_date) <= date.today():
                    return False
            except ValueError:
                pass
        return True

    @staticmethod
    def _safe_summary(application: ExpenseApplication) -> str:
        purpose = application.purpose.strip()
        if len(purpose) > 52:
            purpose = f"{purpose[:52]}…"
        amount = (
            f"{application.amount:.2f}元"
            if application.amount is not None
            else "金额待补充"
        )
        return f"{application.expense_type} {amount}：{purpose}"

    def review(
        self,
        application: ExpenseApplication,
    ) -> SemanticReview:
        payload = {
            "当前日期": date.today().isoformat(),
            "已填写事实": {
                "费用类型": application.expense_type,
                "金额": application.amount,
                "发生日期": application.expense_date,
                "用途说明": application.purpose,
                "是否有附件": bool(application.attachment_id),
            },
        }
        response = self.llm.invoke(
            [
                ("system", self.SYSTEM_PROMPT),
                (
                    "human",
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                    ),
                ),
            ]
        )
        raw = response.content
        if isinstance(raw, list):
            raw = "".join(
                str(item.get("text", ""))
                if isinstance(item, dict)
                else str(item)
                for item in raw
            )
        text = str(raw).strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        parsed: dict[str, Any] = json.loads(text)
        risks = [
            str(item).strip()
            for item in parsed.get("risk_hints", [])
            if str(item).strip()
        ][:3]
        suggestions = [
            str(item).strip()
            for item in parsed.get("suggestions", [])
            if str(item).strip()
        ][:3]
        risks = [
            item
            for item in risks
            if self._is_fact_consistent(item, application)
        ]
        suggestions = [
            item
            for item in suggestions
            if self._is_fact_consistent(item, application)
        ]
        return SemanticReview(
            mode="llm",
            summary=self._safe_summary(application),
            risk_hints=risks,
            suggestions=suggestions,
        )


class ResilientPurposeReviewer:
    def __init__(self, primary: Any, fallback: Any):
        self.primary = primary
        self.fallback = fallback

    def review(
        self,
        application: ExpenseApplication,
    ) -> SemanticReview:
        try:
            return self.primary.review(application)
        except Exception:
            result = self.fallback.review(application)
            result.mode = "rule_fallback_after_llm_error"
            return result
