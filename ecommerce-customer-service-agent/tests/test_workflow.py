from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecommerce_agent.memory import InMemoryConversationStore
from ecommerce_agent.models import ToolResult
from ecommerce_agent.rag import KeywordKnowledgeService
from ecommerce_agent.router import RuleBasedRouter
from ecommerce_agent.tools import SafeToolExecutor
from ecommerce_agent.workflow import AgentWorkflow


class FakeAPI:
    def query_order(self, order_id, user_id):
        if order_id == "DD9999":
            return ToolResult(False, "ORDER_NOT_FOUND", "未找到订单")
        if user_id != "U1001":
            return ToolResult(False, "ACCESS_DENIED", "无权查看订单", http_status=403)
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
        if user_id != "U1001":
            return ToolResult(False, "ACCESS_DENIED", "无权查看订单", http_status=403)
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


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.memory = InMemoryConversationStore()
        self.workflow = AgentWorkflow(
            RuleBasedRouter(),
            SafeToolExecutor(FakeAPI()),
            KeywordKnowledgeService(ROOT / "data" / "ecommerce_knowledge_base.txt"),
            self.memory,
        )

    def test_rag_rule_question(self):
        result = self.workflow.run("衣服洗过还能退吗？", "s1", "U1001")
        self.assertEqual("rag", result.path)
        self.assertTrue(result.success)

    def test_high_risk_goes_to_human(self):
        result = self.workflow.run("质量太差了，我要投诉平台！", "s1", "U1001")
        self.assertEqual("human", result.path)

    def test_missing_order_id_then_resume_in_next_turn(self):
        first = self.workflow.run("我的订单发货了吗？", "s1", "U1001")
        second = self.workflow.run("DD1001", "s1", "U1001")
        self.assertEqual("clarify", first.path)
        self.assertEqual("tool", second.path)
        self.assertIn("已发货", second.answer)

    def test_context_is_isolated_by_session(self):
        self.workflow.run("我的订单发货了吗？", "session-a", "U1001")
        other = self.workflow.run("DD1001", "session-b", "U1001")
        self.assertNotEqual("tool", other.path)

    def test_order_ownership_is_checked(self):
        result = self.workflow.run("DD1001发货了吗？", "s1", "U2002")
        self.assertFalse(result.success)
        self.assertEqual("ACCESS_DENIED", result.error_code)

    def test_logistics_tool(self):
        result = self.workflow.run("DD1001的物流到哪里了？", "s1", "U1001")
        self.assertEqual("tool", result.path)
        self.assertIn("杭州转运中心", result.answer)

    def test_inventory_tool(self):
        result = self.workflow.run("DRESS-BLACK-M还有库存吗？", "s1", "U1001")
        self.assertEqual("tool", result.path)
        self.assertIn("26", result.answer)

    def test_unknown_tool_is_blocked(self):
        from ecommerce_agent.models import Route

        result = SafeToolExecutor(FakeAPI()).execute(
            Route(True, "delete_order_tool", {"order_id": "DD1001"}), "U1001"
        )
        self.assertEqual("TOOL_NOT_ALLOWED", result.error_code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
