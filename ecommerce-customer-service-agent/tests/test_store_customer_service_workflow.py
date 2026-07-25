from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecommerce_agent.memory import InMemoryConversationStore
from ecommerce_agent.models import ToolResult
from ecommerce_agent.router import RuleBasedRouter
from ecommerce_agent.tools import SafeToolExecutor
from store_customer_service.workflow import AdaptiveCustomerWorkflow


class FakeConversationResponder:
    def __init__(self):
        self.questions = []

    def respond(self, question, history):
        self.questions.append(question)
        if question == "阁下又该如何应对":
            return "阁下请出招，我洗耳恭听。"
        return None


class FakeKnowledge:
    def answer(self, question):
        if "什么时候发货" in question:
            return {
                "matched": True,
                "answer": "常规现货商品一般在付款后48小时内发货。",
                "sources": ["发货时效规则"],
            }
        return {"matched": False, "answer": "", "sources": []}


class FakeAPI:
    def query_order(self, order_id, user_id):
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
        raise AssertionError("unexpected logistics call")

    def query_inventory(self, sku):
        raise AssertionError("unexpected inventory call")

    def query_refund(self, order_id, user_id):
        raise AssertionError("unexpected refund call")


class StoreCustomerServiceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.responder = FakeConversationResponder()
        self.workflow = AdaptiveCustomerWorkflow(
            router=RuleBasedRouter(),
            tool_executor=SafeToolExecutor(FakeAPI()),
            knowledge_service=FakeKnowledge(),
            memory_store=InMemoryConversationStore(),
            conversation_responder=self.responder,
        )

    def test_arbitrary_expression_uses_semantic_conversation_layer(self):
        result = self.workflow.run(
            "阁下又该如何应对",
            "conversation",
            "U1001",
        )

        self.assertEqual("conversation", result.path)
        self.assertIn("洗耳恭听", result.answer)

    def test_business_question_returns_to_knowledge_service(self):
        result = self.workflow.run(
            "你们什么时候发货？",
            "policy",
            "U1001",
        )

        self.assertEqual("rag", result.path)
        self.assertIn("48小时", result.answer)

    def test_tool_path_does_not_call_conversation_layer(self):
        result = self.workflow.run(
            "DD1001发货了吗？",
            "tool",
            "U1001",
        )

        self.assertEqual("tool", result.path)
        self.assertIn("已发货", result.answer)
        self.assertEqual([], self.responder.questions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
