from __future__ import annotations

from typing import Any

from .models import ExpenseApplication, UserIdentity


class StructuredExtractor:
    """把表单或工作流结构化输出标准化，身份字段只信任服务端会话。"""

    TYPE_ALIASES = {
        "交通": "交通费",
        "交通费": "交通费",
        "餐饮": "餐饮费",
        "餐饮费": "餐饮费",
        "差旅": "差旅费",
        "差旅费": "差旅费",
        "办公": "办公费",
        "办公费": "办公费",
    }

    def extract(
        self,
        payload: dict[str, Any],
        identity: UserIdentity,
    ) -> ExpenseApplication:
        raw_amount = payload.get("amount")
        try:
            amount = (
                float(raw_amount)
                if raw_amount not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            amount = None
        raw_type = str(payload.get("expense_type", "")).strip()
        return ExpenseApplication(
            employee_id=identity.user_id,
            applicant_name=identity.name,
            department=identity.department,
            manager_id=identity.manager_id,
            expense_type=self.TYPE_ALIASES.get(raw_type, raw_type),
            amount=amount,
            invoice_no=str(payload.get("invoice_no", "")).strip().upper(),
            expense_date=str(payload.get("expense_date", "")).strip(),
            purpose=str(payload.get("purpose", "")).strip(),
            attachment_id=str(
                payload.get("attachment_id", "")
            ).strip(),
            attachment_name=str(
                payload.get("attachment_name", "")
            ).strip(),
        )
