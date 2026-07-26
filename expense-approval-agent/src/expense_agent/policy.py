from __future__ import annotations

import math
from datetime import date

from .models import ApprovalDecision, ExpenseApplication


class ApprovalPolicyEngine:
    ALLOWED_TYPES = {"交通费", "餐饮费", "差旅费", "办公费"}
    REQUIRED_FIELDS = {
        "employee_id": "员工身份",
        "expense_type": "费用类型",
        "amount": "金额",
        "invoice_no": "发票号码",
        "expense_date": "发生日期",
        "purpose": "用途说明",
    }

    def evaluate(
        self,
        application: ExpenseApplication,
        database,
        *,
        exclude_application_id: int | None = None,
    ) -> ApprovalDecision:
        missing = []
        for field, label in self.REQUIRED_FIELDS.items():
            value = getattr(application, field)
            if value in (None, ""):
                missing.append(label)
        if missing:
            return self._failure(
                "退回补充材料",
                "returned",
                "中",
                ["报销申请缺少必填字段"],
                "由申请人补齐材料后重新提交",
                "MISSING_FIELDS",
                missing,
            )

        if (
            application.amount is None
            or not math.isfinite(application.amount)
            or application.amount <= 0
        ):
            return self._failure(
                "退回修改",
                "returned",
                "中",
                ["报销金额必须为大于0的有效数字"],
                "修改金额后重新提交",
                "INVALID_AMOUNT",
                ["有效金额"],
            )

        try:
            expense_date = date.fromisoformat(application.expense_date)
        except ValueError:
            return self._failure(
                "退回修改",
                "returned",
                "中",
                ["费用发生日期格式无效"],
                "填写真实费用发生日期后重新提交",
                "INVALID_EXPENSE_DATE",
                ["有效发生日期"],
            )
        if expense_date > date.today():
            return self._failure(
                "退回修改",
                "returned",
                "中",
                ["费用发生日期不能晚于当前日期"],
                "核对日期后重新提交",
                "FUTURE_EXPENSE_DATE",
                ["真实发生日期"],
            )

        normalized_purpose = "".join(
            application.purpose.split()
        )
        if (
            len(normalized_purpose) < 6
            or len(set(normalized_purpose)) <= 2
        ):
            return self._failure(
                "退回补充材料",
                "returned",
                "中",
                ["用途说明过于简略，无法核验业务关联性"],
                "补充业务目的、对象或行程信息后重新提交",
                "PURPOSE_TOO_VAGUE",
                ["完整用途说明"],
            )

        employee = database.get_employee(application.employee_id)
        if employee is None:
            return self._failure(
                "身份核验失败",
                "rejected",
                "高",
                ["未找到当前登录员工信息"],
                "由人力或财务核实员工身份",
                "EMPLOYEE_NOT_FOUND",
                need_human=True,
            )
        if not employee["active"]:
            return self._failure(
                "身份核验失败",
                "rejected",
                "高",
                ["员工当前为非在职状态"],
                "由人力和财务共同核实",
                "EMPLOYEE_INACTIVE",
                need_human=True,
            )
        if employee["role"] != "employee":
            return self._failure(
                "身份核验失败",
                "rejected",
                "高",
                ["当前演示身份不是可提交报销的员工账号"],
                "切换至员工身份后提交",
                "APPLICANT_ROLE_INVALID",
            )

        if application.expense_type not in self.ALLOWED_TYPES:
            return self._failure(
                "退回修改",
                "returned",
                "中",
                ["费用类型不在标准分类中"],
                "选择标准费用类型或联系财务确认归类",
                "UNKNOWN_EXPENSE_TYPE",
                ["标准费用类型"],
            )
        if database.invoice_exists(
            application.invoice_no,
            exclude_application_id=exclude_application_id,
        ):
            return self._failure(
                "重复报销拦截",
                "rejected",
                "高",
                ["发票号码已存在，疑似重复报销"],
                "由财务核查原申请和发票",
                "DUPLICATE_INVOICE",
                need_human=True,
            )

        budget = database.get_budget(application.department)
        remaining = (
            None
            if budget is None
            else budget["monthly_budget"] - budget["used_amount"]
        )
        if remaining is None or application.amount > remaining:
            return ApprovalDecision(
                True,
                None,
                "财务复核",
                "pending_finance",
                "高",
                ["部门剩余预算不足或预算数据无法确认"],
                need_human_review=True,
                next_step="进入财务待办，由财务确认预算或追加额度",
                error_code="BUDGET_REVIEW",
            )
        if application.amount <= 1000:
            return ApprovalDecision(
                True,
                None,
                "自动预审通过",
                "approved",
                "低",
                [
                    "材料齐全、员工有效、预算充足且金额不超过1000元"
                ],
                next_step="预审流程已完成；该结果不代表真实企业付款承诺",
            )
        if application.amount <= 5000 and application.manager_id:
            return ApprovalDecision(
                True,
                None,
                "主管审批",
                "pending_manager",
                "中",
                ["金额在1000至5000元之间"],
                need_human_review=True,
                next_step=f"进入直属主管{application.manager_id}待办",
            )
        return ApprovalDecision(
            True,
            None,
            "财务审批",
            "pending_finance",
            "高",
            ["金额超过5000元或未配置直属主管"],
            need_human_review=True,
            next_step="进入财务负责人待办",
        )

    @staticmethod
    def _failure(
        decision: str,
        status: str,
        risk_level: str,
        reasons: list[str],
        next_step: str,
        error_code: str,
        missing_fields: list[str] | None = None,
        *,
        need_human: bool = False,
    ) -> ApprovalDecision:
        return ApprovalDecision(
            False,
            None,
            decision,
            status,
            risk_level,
            reasons,
            missing_fields or [],
            need_human,
            next_step,
            error_code=error_code,
        )
