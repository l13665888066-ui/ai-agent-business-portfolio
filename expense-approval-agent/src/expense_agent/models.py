from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExpenseApplication:
    employee_id: str = ""
    expense_type: str = ""
    amount: float | None = None
    invoice_no: str = ""
    expense_date: str = ""
    purpose: str = ""
    department: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApprovalDecision:
    success: bool
    application_id: int | None
    decision: str
    risk_level: str
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    need_human_review: bool = False
    next_step: str = ""
    policy_sources: list[str] = field(default_factory=list)
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
