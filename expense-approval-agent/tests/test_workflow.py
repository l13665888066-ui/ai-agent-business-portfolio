from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from expense_agent.database import Database
from expense_agent.extractor import StructuredExtractor
from expense_agent.knowledge import PolicyKnowledgeService
from expense_agent.policy import ApprovalPolicyEngine
from expense_agent.semantic_review import LocalPurposeReviewer
from expense_agent.workflow import ExpenseApprovalWorkflow


class ExpenseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.workflow = ExpenseApprovalWorkflow(
            StructuredExtractor(),
            ApprovalPolicyEngine(),
            PolicyKnowledgeService(
                ROOT / "data" / "expense_policy.md"
            ),
            LocalPurposeReviewer(),
            self.db,
        )

    @staticmethod
    def application(**overrides):
        base = {
            "expense_type": "交通费",
            "amount": 680,
            "invoice_no": "INV-001",
            "expense_date": "2026-07-01",
            "purpose": "拜访客户产生的高铁交通费用",
        }
        base.update(overrides)
        return base

    def submit(self, **overrides):
        return self.workflow.submit(
            self.application(**overrides),
            "E1001",
        )

    def test_small_complete_application_is_auto_approved(self):
        before = self.db.get_budget("销售部")["used_amount"]
        result = self.submit()
        after = self.db.get_budget("销售部")["used_amount"]

        self.assertEqual("approved", result.status)
        self.assertEqual("自动预审通过", result.decision)
        self.assertIsNotNone(result.application_id)
        self.assertEqual(before + 680, after)

    def test_identity_fields_do_not_trust_payload(self):
        result = self.workflow.submit(
            self.application(
                employee_id="E1002",
                department="市场部",
            ),
            "E1001",
        )
        stored = self.db.get_application(result.application_id)

        self.assertEqual("E1001", stored["employee_id"])
        self.assertEqual("销售部", stored["department"])
        self.assertEqual("M2001", stored["manager_id"])

    def test_missing_invoice_is_returned_before_create(self):
        result = self.submit(invoice_no="")

        self.assertEqual("MISSING_FIELDS", result.error_code)
        self.assertIn("发票号码", result.missing_fields)
        self.assertIsNone(result.application_id)

    def test_future_expense_date_is_rejected(self):
        result = self.submit(
            invoice_no="INV-FUTURE",
            expense_date="2099-01-01",
        )

        self.assertEqual(
            "FUTURE_EXPENSE_DATE",
            result.error_code,
        )
        self.assertIsNone(result.application_id)

    def test_vague_purpose_is_returned(self):
        result = self.submit(
            invoice_no="INV-VAGUE",
            purpose="哈哈",
        )

        self.assertEqual("PURPOSE_TOO_VAGUE", result.error_code)
        self.assertIn("完整用途说明", result.missing_fields)

    def test_medium_amount_goes_to_assigned_manager(self):
        result = self.submit(
            amount=3200,
            invoice_no="INV-MANAGER",
        )
        stored = self.db.get_application(result.application_id)

        self.assertEqual("pending_manager", result.status)
        self.assertEqual("manager", stored["current_approver_role"])
        self.assertEqual("M2001", stored["manager_id"])

    def test_assigned_manager_can_approve(self):
        result = self.submit(
            amount=3200,
            invoice_no="INV-APPROVE",
        )
        updated = self.workflow.act(
            result.application_id,
            "M2001",
            "approve",
            "费用与客户拜访计划一致",
        )

        self.assertEqual("approved", updated["status"])
        actions = self.db.list_actions(result.application_id)
        self.assertEqual(
            ["submit", "approve"],
            [item["action"] for item in actions],
        )

    def test_unassigned_manager_is_forbidden(self):
        result = self.submit(
            amount=3200,
            invoice_no="INV-FORBIDDEN",
        )

        with self.assertRaises(PermissionError):
            self.workflow.act(
                result.application_id,
                "M2002",
                "approve",
                "",
            )

    def test_return_requires_comment(self):
        result = self.submit(
            amount=3200,
            invoice_no="INV-COMMENT",
        )

        with self.assertRaises(ValueError):
            self.workflow.act(
                result.application_id,
                "M2001",
                "return",
                "",
            )

    def test_employee_can_resubmit_returned_application(self):
        result = self.submit(
            amount=3200,
            invoice_no="INV-RESUBMIT",
        )
        self.workflow.act(
            result.application_id,
            "M2001",
            "return",
            "请补充客户名称",
        )
        resubmitted = self.workflow.resubmit(
            result.application_id,
            self.application(
                amount=3200,
                invoice_no="INV-RESUBMIT",
                purpose="拜访杭州客户并沟通年度合作产生的交通费",
            ),
            "E1001",
        )

        self.assertTrue(resubmitted.success)
        self.assertEqual("pending_manager", resubmitted.status)
        actions = self.db.list_actions(result.application_id)
        self.assertEqual(
            ["submit", "return", "resubmit"],
            [item["action"] for item in actions],
        )

    def test_other_employee_cannot_resubmit(self):
        result = self.submit(
            amount=3200,
            invoice_no="INV-OWNER",
        )
        self.workflow.act(
            result.application_id,
            "M2001",
            "return",
            "补充材料",
        )
        other = self.workflow.resubmit(
            result.application_id,
            self.application(
                invoice_no="INV-OWNER",
                purpose="市场活动产生的交通费用说明",
            ),
            "E1002",
        )

        self.assertEqual("OWNER_FORBIDDEN", other.error_code)

    def test_large_amount_goes_to_finance(self):
        result = self.submit(
            amount=8000,
            invoice_no="INV-FINANCE",
        )

        self.assertEqual("pending_finance", result.status)
        self.assertTrue(result.need_human_review)

    def test_finance_can_approve_large_amount(self):
        result = self.submit(
            amount=8000,
            invoice_no="INV-FINANCE-APPROVE",
        )
        updated = self.workflow.act(
            result.application_id,
            "F3001",
            "approve",
            "预算和业务材料已复核",
        )

        self.assertEqual("approved", updated["status"])

    def test_budget_shortage_goes_to_finance(self):
        result = self.workflow.submit(
            self.application(
                amount=3000,
                invoice_no="INV-BUDGET",
                purpose="市场活动现场物料运输交通费用",
            ),
            "E1002",
        )

        self.assertEqual("BUDGET_REVIEW", result.error_code)
        self.assertEqual("pending_finance", result.status)

    def test_duplicate_invoice_is_blocked(self):
        self.submit(invoice_no="INV-DUP")
        duplicate = self.submit(invoice_no="INV-DUP")

        self.assertEqual(
            "DUPLICATE_INVOICE",
            duplicate.error_code,
        )
        self.assertIsNone(duplicate.application_id)

    def test_inactive_identity_cannot_submit(self):
        result = self.workflow.submit(
            self.application(invoice_no="INV-INACTIVE"),
            "E1003",
        )

        self.assertEqual("IDENTITY_INACTIVE", result.error_code)

    def test_application_lists_are_role_scoped(self):
        manager_item = self.submit(
            amount=3200,
            invoice_no="INV-LIST-M",
        )
        finance_item = self.submit(
            amount=8000,
            invoice_no="INV-LIST-F",
        )
        manager = self.db.get_identity("M2001")
        finance = self.db.get_identity("F3001")
        employee = self.db.get_identity("E1001")

        manager_pending = self.db.list_applications(
            manager,
            "pending",
        )
        finance_pending = self.db.list_applications(
            finance,
            "pending",
        )
        employee_all = self.db.list_applications(
            employee,
            "all",
        )

        self.assertEqual(
            [manager_item.application_id],
            [item["id"] for item in manager_pending],
        )
        self.assertEqual(
            [finance_item.application_id],
            [item["id"] for item in finance_pending],
        )
        self.assertEqual(2, len(employee_all))

    def test_attachment_must_belong_to_current_employee(self):
        self.db.add_attachment(
            "ATT-OTHER",
            "invoice.pdf",
            "stored.pdf",
            "application/pdf",
            100,
            "E1002",
        )
        result = self.submit(
            invoice_no="INV-ATT",
            attachment_id="ATT-OTHER",
        )

        self.assertEqual(
            "ATTACHMENT_FORBIDDEN",
            result.error_code,
        )

    def test_policy_sources_and_semantic_review_are_saved(self):
        result = self.submit(invoice_no="INV-EVIDENCE")
        stored = self.db.get_application(result.application_id)

        self.assertTrue(stored["policy_sources"])
        self.assertEqual(
            "rule_fallback",
            stored["semantic_review"]["mode"],
        )

    def test_audit_is_bound_to_application(self):
        result = self.submit(invoice_no="INV-AUDIT")
        audit = self.db.list_audit(result.application_id)

        self.assertEqual(
            "precheck_completed",
            audit[0]["event"],
        )
        self.assertEqual("E1001", audit[0]["actor_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
