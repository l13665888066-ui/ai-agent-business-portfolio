from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from store_customer_service.knowledge import ResilientKnowledgeService


class BrokenVectorKnowledge:
    def answer(self, question):
        raise RuntimeError("simulated embedding outage")


class LocalKnowledge:
    def answer(self, question):
        return {
            "matched": True,
            "answer": "常规现货商品一般在付款后48小时内发货。",
            "sources": ["发货时效规则"],
        }


class ResilientKnowledgeTests(unittest.TestCase):
    def test_vector_failure_falls_back_without_breaking_conversation(self):
        service = ResilientKnowledgeService(
            BrokenVectorKnowledge(),
            LocalKnowledge(),
        )

        result = service.answer("你们什么时候发货？")

        self.assertTrue(result["matched"])
        self.assertIn("48小时", result["answer"])
        self.assertTrue(result["degraded"])
        self.assertEqual("RuntimeError", result["degraded_reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
