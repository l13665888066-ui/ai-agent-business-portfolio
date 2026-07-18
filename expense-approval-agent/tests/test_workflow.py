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
from expense_agent.workflow import ExpenseApprovalWorkflow


class ExpenseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.workflow = ExpenseApprovalWorkflow(
            StructuredExtractor(),
            ApprovalPolicyEngine(),
            PolicyKnowledgeService(ROOT / "data" / "expense_policy.md"),
            self.db,
        )

    @staticmethod
    def application(**overrides):
        base = {
            "employee_id": "E1001",
            "expense_type": "交通费",
            "amount": 680,
            "invoice_no": "INV-001",
            "expense_date": "2026-07-01",
            "purpose": "拜访客户产生的高铁费用",
        }
        base.update(overrides)
        return base

    def test_small_complete_application_passes_precheck(self):
        result = self.workflow.run(self.application())
        self.assertEqual("初步通过", result.decision)
        self.assertIsNotNone(result.application_id)

    def test_missing_invoice_is_returned(self):
        result = self.workflow.run(self.application(invoice_no=""))
        self.assertEqual("MISSING_FIELDS", result.error_code)
        self.assertIn("发票号码", result.missing_fields)

    def test_medium_amount_goes_to_manager(self):
        result = self.workflow.run(self.application(amount=3200, invoice_no="INV-002"))
        self.assertEqual("主管复核", result.decision)
        self.assertTrue(result.need_human_review)

    def test_large_amount_goes_to_finance(self):
        result = self.workflow.run(self.application(amount=8000, invoice_no="INV-003"))
        self.assertEqual("财务复核", result.decision)

    def test_duplicate_invoice_is_blocked(self):
        self.workflow.run(self.application(invoice_no="INV-DUP"))
        duplicate = self.workflow.run(self.application(invoice_no="INV-DUP"))
        self.assertEqual("DUPLICATE_INVOICE", duplicate.error_code)

    def test_inactive_employee_needs_human_review(self):
        result = self.workflow.run(self.application(employee_id="E1003"))
        self.assertEqual("EMPLOYEE_INACTIVE", result.error_code)
        self.assertTrue(result.need_human_review)

    def test_budget_shortage_goes_to_finance(self):
        result = self.workflow.run(
            self.application(
                employee_id="E1002", amount=3000, invoice_no="INV-BUDGET"
            )
        )
        self.assertEqual("BUDGET_REVIEW", result.error_code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
