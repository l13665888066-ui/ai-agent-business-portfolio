from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from store_customer_service.knowledge_output import (
    CustomerFriendlyKnowledgeService,
)


class InternalKnowledge:
    def answer(self, question):
        return {
            "matched": True,
            "answer": (
                "根据店铺规则：适用问题：用户询问什么时候发货。\n"
                "规则内容：常规现货商品一般在付款后48小时内发货；"
                "预售商品按页面标注时间发货。\n"
                "客服回复边界：不得承诺一定当天发货。"
            ),
            "sources": ["发货时效规则"],
        }


class CustomerFriendlyKnowledgeTests(unittest.TestCase):
    def test_internal_fields_are_not_exposed_to_customer(self):
        result = CustomerFriendlyKnowledgeService(
            InternalKnowledge()
        ).answer("你们什么时候发货？")

        self.assertTrue(result["matched"])
        self.assertIn("48小时", result["answer"])
        self.assertNotIn("适用问题", result["answer"])
        self.assertNotIn("规则内容", result["answer"])
        self.assertNotIn("客服回复边界", result["answer"])
        self.assertEqual(["发货时效规则"], result["sources"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
