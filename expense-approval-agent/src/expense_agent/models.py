from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    name: str
    role: str
    department: str
    manager_id: str = ""
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExpenseApplication:
    employee_id: str = ""
    applicant_name: str = ""
    department: str = ""
    manager_id: str = ""
    expense_type: str = ""
    amount: float | None = None
    invoice_no: str = ""
    expense_date: str = ""
    purpose: str = ""
    attachment_id: str = ""
    attachment_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticReview:
    mode: str = "rule_fallback"
    summary: str = ""
    risk_hints: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApprovalDecision:
    success: bool
    application_id: int | None
    decision: str
    status: str
    risk_level: str
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    need_human_review: bool = False
    next_step: str = ""
    policy_sources: list[dict[str, Any]] = field(default_factory=list)
    semantic_review: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
