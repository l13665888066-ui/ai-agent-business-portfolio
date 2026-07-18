from __future__ import annotations

from .models import ApprovalDecision, ExpenseApplication


class ApprovalPolicyEngine:
    ALLOWED_TYPES = {"交通费", "餐饮费", "差旅费", "办公费"}
    REQUIRED_FIELDS = {
        "employee_id": "员工编号",
        "expense_type": "费用类型",
        "amount": "金额",
        "invoice_no": "发票号码",
        "expense_date": "发生日期",
        "purpose": "用途说明",
    }

    def evaluate(self, application: ExpenseApplication, database) -> ApprovalDecision:
        missing = []
        for field, label in self.REQUIRED_FIELDS.items():
            value = getattr(application, field)
            if value in (None, ""):
                missing.append(label)
        if missing:
            return ApprovalDecision(
                False,
                None,
                "退回补充材料",
                "中",
                ["报销申请缺少必填字段"],
                missing,
                False,
                "由申请人补齐材料后重新提交",
                error_code="MISSING_FIELDS",
            )

        if application.amount is None or application.amount <= 0:
            return ApprovalDecision(
                False,
                None,
                "退回修改",
                "中",
                ["报销金额必须大于0"],
                ["有效金额"],
                False,
                "修改金额后重新提交",
                error_code="INVALID_AMOUNT",
            )

        employee = database.get_employee(application.employee_id)
        if employee is None:
            return ApprovalDecision(False, None, "人工复核", "高", ["未找到员工信息"], need_human_review=True, next_step="由人力或财务核实员工身份", error_code="EMPLOYEE_NOT_FOUND")
        if not employee["active"]:
            return ApprovalDecision(False, None, "人工复核", "高", ["员工当前为非在职状态"], need_human_review=True, next_step="由人力和财务共同核实", error_code="EMPLOYEE_INACTIVE")

        application.department = employee["department"]
        if application.expense_type not in self.ALLOWED_TYPES:
            return ApprovalDecision(False, None, "人工复核", "中", ["费用类型不在标准分类中"], need_human_review=True, next_step="由财务确认费用归类", error_code="UNKNOWN_EXPENSE_TYPE")
        if database.invoice_exists(application.invoice_no):
            return ApprovalDecision(False, None, "人工复核", "高", ["发票号码已存在，可能重复报销"], need_human_review=True, next_step="由财务核查原申请和发票", error_code="DUPLICATE_INVOICE")

        budget = database.get_budget(application.department)
        remaining = None if budget is None else budget["monthly_budget"] - budget["used_amount"]
        if remaining is None or application.amount > remaining:
            return ApprovalDecision(True, None, "财务复核", "高", ["部门剩余预算不足或无法确认"], need_human_review=True, next_step="提交财务核实预算并决定是否追加", error_code="BUDGET_REVIEW")
        if application.amount <= 1000:
            return ApprovalDecision(True, None, "初步通过", "低", ["材料齐全、员工有效、预算充足且金额不超过1000元"], next_step="进入后续报销流程，不代表最终付款承诺")
        if application.amount <= 5000:
            return ApprovalDecision(True, None, "主管复核", "中", ["金额在1000至5000元之间"], need_human_review=True, next_step=f"提交直属主管{employee['manager_id']}复核")
        return ApprovalDecision(True, None, "财务复核", "高", ["金额超过5000元"], need_human_review=True, next_step="提交财务负责人复核")
