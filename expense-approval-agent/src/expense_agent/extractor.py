from __future__ import annotations

from typing import Any

from .models import ExpenseApplication


class StructuredExtractor:
    """表单或Dify结构化输出进入业务层前的统一标准化。"""

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

    def extract(self, payload: dict[str, Any]) -> ExpenseApplication:
        raw_amount = payload.get("amount")
        try:
            amount = float(raw_amount) if raw_amount not in (None, "") else None
        except (TypeError, ValueError):
            amount = None
        raw_type = str(payload.get("expense_type", "")).strip()
        return ExpenseApplication(
            employee_id=str(payload.get("employee_id", "")).strip().upper(),
            expense_type=self.TYPE_ALIASES.get(raw_type, raw_type),
            amount=amount,
            invoice_no=str(payload.get("invoice_no", "")).strip().upper(),
            expense_date=str(payload.get("expense_date", "")).strip(),
            purpose=str(payload.get("purpose", "")).strip(),
            department=str(payload.get("department", "")).strip(),
        )
