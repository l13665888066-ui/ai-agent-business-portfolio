from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecommerce_agent.conversation_workflow import CustomerConversationWorkflow
from ecommerce_agent.memory import InMemoryConversationStore
from ecommerce_agent.models import ToolResult
from ecommerce_agent.router import RuleBasedRouter
from ecommerce_agent.tools import SafeToolExecutor


class EmptyKnowledgeService:
    def answer(self, question):
        return {
            "matched": False,
            "answer": "内部知识库未命中",
            "sources": [],
        }


class ConversationAPI:
    def query_order(self, order_id, user_id):
        if order_id == "DD1002":
            return ToolResult(
                False,
                "ACCESS_DENIED",
                "无权查看订单",
                http_status=403,
            )
        if order_id == "DD8898":
            return ToolResult(
                False,
                "ORDER_NOT_FOUND",
                "未找到订单",
                http_status=200,
            )
        return ToolResult(
            True,
            None,
            "查询成功",
            {
                "order_id": order_id,
                "order_status": "已发货",
                "pay_status": "已支付",
            },
            200,
        )

    def query_logistics(self, order_id, user_id):
        return ToolResult(
            True,
            None,
            "查询成功",
            {
                "order_id": order_id,
                "company": "中通快递",
                "logistics_status": "运输中",
                "latest_trace": "已到达杭州转运中心",
            },
            200,
        )

    def query_inventory(self, sku):
        return ToolResult(
            True,
            None,
            "查询成功",
            {"sku": sku, "available_stock": 26},
            200,
        )

    def query_refund(self, order_id, user_id):
        return ToolResult(
            True,
            None,
            "查询成功",
            {"order_id": order_id, "refund_status": "审核中"},
            200,
        )


class CustomerConversationTests(unittest.TestCase):
    def setUp(self):
        self.workflow = CustomerConversationWorkflow(
            RuleBasedRouter(),
            SafeToolExecutor(ConversationAPI()),
            EmptyKnowledgeService(),
            InMemoryConversationStore(),
        )

    def test_greeting_returns_natural_service_reply(self):
        result = self.workflow.run("你好", "greeting", "U1001")
        self.assertEqual("smalltalk", result.path)
        self.assertIn("您好", result.answer)
        self.assertNotIn("知识库", result.answer)

    def test_unknown_question_returns_capability_guidance(self):
        result = self.workflow.run("你觉得今天怎么样", "unknown", "U1001")
        self.assertEqual("guidance", result.path)
        self.assertIn("订单", result.answer)
        self.assertNotIn("知识库", result.answer)

    def test_failed_order_lookup_keeps_original_task_context(self):
        first = self.workflow.run("我的订单发货了吗？", "repair", "U1001")
        denied = self.workflow.run("DD1002", "repair", "U1001")
        missing = self.workflow.run("DD8898", "repair", "U1001")
        success = self.workflow.run("DD1001", "repair", "U1001")

        self.assertEqual("clarify", first.path)
        self.assertEqual("ACCESS_DENIED", denied.error_code)
        self.assertIn("本人", denied.answer)
        self.assertEqual("tool", missing.path)
        self.assertEqual("ORDER_NOT_FOUND", missing.error_code)
        self.assertIn("DD8898", missing.answer)
        self.assertNotIn("知识库", missing.answer)
        self.assertTrue(success.success)
        self.assertIn("已发货", success.answer)

    def test_bare_order_number_can_reuse_last_successful_intent(self):
        first = self.workflow.run("DD1001发货了吗？", "reuse", "U1001")
        second = self.workflow.run("DD1003", "reuse", "U1001")
        self.assertTrue(first.success)
        self.assertEqual("tool", second.path)
        self.assertIn("DD1003", second.answer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
