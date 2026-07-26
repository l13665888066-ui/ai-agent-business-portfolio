from __future__ import annotations

import sqlite3
from typing import Any

from .database import BudgetUnavailableError
from .models import ApprovalDecision, UserIdentity


class ExpenseApprovalWorkflow:
    def __init__(
        self,
        extractor,
        policy_engine,
        knowledge_service,
        semantic_reviewer,
        database,
    ):
        self.extractor = extractor
        self.policy_engine = policy_engine
        self.knowledge_service = knowledge_service
        self.semantic_reviewer = semantic_reviewer
        self.database = database

    def submit(
        self,
        payload: dict[str, Any],
        actor_id: str,
    ) -> ApprovalDecision:
        actor = self.database.get_identity(actor_id)
        if actor is None:
            return self._identity_failure(
                "当前登录身份不存在",
                "IDENTITY_NOT_FOUND",
            )
        if not actor.active:
            return self._identity_failure(
                "当前登录身份已停用",
                "IDENTITY_INACTIVE",
            )

        application = self.extractor.extract(payload, actor)
        attachment = None
        if application.attachment_id:
            attachment = self.database.attachment_belongs_to(
                application.attachment_id,
                actor.user_id,
            )
            if attachment is None:
                return ApprovalDecision(
                    False,
                    None,
                    "附件校验失败",
                    "returned",
                    "中",
                    ["附件不存在或不属于当前登录用户"],
                    ["重新上传票据附件"],
                    False,
                    "重新上传后提交",
                    error_code="ATTACHMENT_FORBIDDEN",
                )
            application.attachment_name = attachment[
                "original_name"
            ]

        decision = self.policy_engine.evaluate(
            application,
            self.database,
        )
        query = (
            f"{application.expense_type} "
            f"{application.purpose}"
        ).strip()
        decision.policy_sources = (
            self.knowledge_service.retrieve(query)
            if query
            else []
        )
        if application.purpose:
            decision.semantic_review = (
                self.semantic_reviewer.review(
                    application
                ).to_dict()
            )

        if not decision.success:
            self.database.add_audit(
                None,
                actor,
                "submission_rejected_before_create",
                decision.to_dict(),
            )
            return decision

        try:
            application_id = self.database.create_application(
                application,
                decision,
                actor,
            )
        except BudgetUnavailableError:
            decision.status = "pending_finance"
            decision.decision = "财务复核"
            decision.risk_level = "高"
            decision.need_human_review = True
            decision.reasons.append(
                "提交写入时预算发生变化，已转财务复核"
            )
            decision.next_step = (
                "进入财务待办，由财务重新确认预算"
            )
            decision.error_code = "BUDGET_CHANGED"
            application_id = self.database.create_application(
                application,
                decision,
                actor,
            )
        except sqlite3.IntegrityError:
            decision.success = False
            decision.decision = "重复报销拦截"
            decision.status = "rejected"
            decision.risk_level = "高"
            decision.reasons = [
                "发票号码在写入时触发唯一约束"
            ]
            decision.need_human_review = True
            decision.next_step = (
                "由财务检查并发提交或重复报销"
            )
            decision.error_code = "DUPLICATE_INVOICE_RACE"
            return decision
        decision.application_id = application_id
        return decision

    def resubmit(
        self,
        application_id: int,
        payload: dict[str, Any],
        actor_id: str,
    ) -> ApprovalDecision:
        actor = self.database.get_identity(actor_id)
        if actor is None:
            return self._identity_failure(
                "当前登录身份不存在",
                "IDENTITY_NOT_FOUND",
            )
        current = self.database.get_application(application_id)
        if current is None:
            return self._identity_failure(
                "未找到报销申请",
                "APPLICATION_NOT_FOUND",
            )
        if current["employee_id"] != actor.user_id:
            return self._identity_failure(
                "只能重新提交自己的报销申请",
                "OWNER_FORBIDDEN",
            )
        if current["status"] != "returned":
            return self._identity_failure(
                "当前申请不处于退回补充状态",
                "APPLICATION_NOT_RETURNED",
            )

        application = self.extractor.extract(payload, actor)
        if application.attachment_id:
            attachment = self.database.attachment_belongs_to(
                application.attachment_id,
                actor.user_id,
            )
            if attachment is None:
                return self._identity_failure(
                    "附件不存在或不属于当前用户",
                    "ATTACHMENT_FORBIDDEN",
                )
            application.attachment_name = attachment[
                "original_name"
            ]

        decision = self.policy_engine.evaluate(
            application,
            self.database,
            exclude_application_id=application_id,
        )
        query = (
            f"{application.expense_type} "
            f"{application.purpose}"
        ).strip()
        decision.policy_sources = (
            self.knowledge_service.retrieve(query)
            if query
            else []
        )
        if application.purpose:
            decision.semantic_review = (
                self.semantic_reviewer.review(
                    application
                ).to_dict()
            )
        if not decision.success:
            return decision

        try:
            self.database.resubmit_application(
                application_id,
                application,
                decision,
                actor,
            )
        except BudgetUnavailableError:
            decision.status = "pending_finance"
            decision.decision = "财务复核"
            decision.risk_level = "高"
            decision.need_human_review = True
            decision.reasons.append(
                "重新提交时预算发生变化，已转财务复核"
            )
            self.database.resubmit_application(
                application_id,
                application,
                decision,
                actor,
            )
        decision.application_id = application_id
        return decision

    def act(
        self,
        application_id: int,
        actor_id: str,
        action: str,
        comment: str,
    ) -> dict[str, Any]:
        actor = self.database.get_identity(actor_id)
        if actor is None or not actor.active:
            raise PermissionError("IDENTITY_FORBIDDEN")
        return self.database.act_on_application(
            application_id,
            actor,
            action,
            comment,
        )

    def run(
        self,
        payload: dict[str, Any],
    ) -> ApprovalDecision:
        """兼容Dify HTTP节点；身份仍由受控employee_id映射。"""
        return self.submit(
            payload,
            str(payload.get("employee_id", "")).upper(),
        )

    @staticmethod
    def _identity_failure(
        reason: str,
        error_code: str,
    ) -> ApprovalDecision:
        return ApprovalDecision(
            False,
            None,
            "无法继续",
            "rejected",
            "高",
            [reason],
            need_human_review=True,
            next_step="切换正确身份或联系管理员",
            error_code=error_code,
        )
