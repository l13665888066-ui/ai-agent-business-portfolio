from __future__ import annotations

import sqlite3
from typing import Any

from .models import ApprovalDecision


class ExpenseApprovalWorkflow:
    def __init__(self, extractor, policy_engine, knowledge_service, database):
        self.extractor = extractor
        self.policy_engine = policy_engine
        self.knowledge_service = knowledge_service
        self.database = database

    def run(self, payload: dict[str, Any]) -> ApprovalDecision:
        application = self.extractor.extract(payload)
        decision = self.policy_engine.evaluate(application, self.database)
        decision.policy_sources = self.knowledge_service.search(application.expense_type)
        self.database.add_audit(
            None,
            "precheck_completed",
            {
                "employee_id": application.employee_id,
                "decision": decision.decision,
                "risk_level": decision.risk_level,
                "error_code": decision.error_code,
            },
        )
        if decision.error_code in {"MISSING_FIELDS", "INVALID_AMOUNT", "EMPLOYEE_NOT_FOUND", "EMPLOYEE_INACTIVE", "UNKNOWN_EXPENSE_TYPE", "DUPLICATE_INVOICE"}:
            return decision
        try:
            application_id = self.database.create_application(application, decision)
        except sqlite3.IntegrityError:
            decision.success = False
            decision.decision = "人工复核"
            decision.risk_level = "高"
            decision.reasons = ["发票号码在写入时触发重复约束"]
            decision.need_human_review = True
            decision.next_step = "由财务检查并发提交或重复报销"
            decision.error_code = "DUPLICATE_INVOICE_RACE"
            return decision
        decision.application_id = application_id
        self.database.add_audit(application_id, "application_created", decision.to_dict())
        return decision
