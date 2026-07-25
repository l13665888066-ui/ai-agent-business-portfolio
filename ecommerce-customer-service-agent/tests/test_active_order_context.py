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


class EmptyKnowledge:
    def answer(self, question):
        return {"matched": False, "answer": "", "sources": []}


class ContextAPI:
    OWNERS = {"DD1001": "U1001", "DD1003": "U1001"}

    def __init__(self):
        self.logistics_calls = []

    def _check_owner(self, order_id, user_id):
        if self.OWNERS.get(order_id) != user_id:
            return ToolResult(
                False,
                "ACCESS_DENIED",
                "无权查看订单",
                http_status=403,
            )
        return None

    def query_order(self, order_id, user_id):
        denied = self._check_owner(order_id, user_id)
        if denied:
            return denied
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
        denied = self._check_owner(order_id, user_id)
        if denied:
            return denied
        self.logistics_calls.append((order_id, user_id))
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
        raise AssertionError("unexpected inventory call")

    def query_refund(self, order_id, user_id):
        denied = self._check_owner(order_id, user_id)
        if denied:
            return denied
        return ToolResult(
            True,
            None,
            "查询成功",
            {"order_id": order_id, "refund_status": "无退款申请"},
            200,
        )


class ActiveOrderContextTests(unittest.TestCase):
    def setUp(self):
        self.api = ContextAPI()
        self.memory = InMemoryConversationStore()
        self.workflow = CustomerConversationWorkflow(
            RuleBasedRouter(),
            SafeToolExecutor(self.api),
            EmptyKnowledge(),
            self.memory,
        )

    def test_followup_reuses_verified_order_for_new_tool(self):
        first = self.workflow.run(
            "DD1001发货了吗？",
            "followup",
            "U1001",
        )
        followup = self.workflow.run(
            "要多久能到啊",
            "followup",
            "U1001",
        )

        self.assertTrue(first.success)
        self.assertEqual("tool", followup.path)
        self.assertEqual(
            "query_logistics_tool",
            followup.route.tool_name,
        )
        self.assertEqual(
            {"order_id": "DD1001"},
            followup.route.tool_args,
        )
        self.assertIn("杭州转运中心", followup.answer)

    def test_explicit_new_order_replaces_active_order(self):
        self.workflow.run("DD1001发货了吗？", "switch", "U1001")
        explicit = self.workflow.run(
            "DD1003的快递到哪了？",
            "switch",
            "U1001",
        )
        followup = self.workflow.run(
            "要多久能到啊",
            "switch",
            "U1001",
        )

        self.assertTrue(explicit.success)
        self.assertEqual("DD1003", followup.route.tool_args["order_id"])
        self.assertEqual(
            [("DD1003", "U1001"), ("DD1003", "U1001")],
            self.api.logistics_calls,
        )

    def test_active_order_is_not_shared_with_another_user(self):
        self.workflow.run("DD1001发货了吗？", "shared", "U1001")

        other_user = self.workflow.run(
            "要多久能到啊",
            "shared",
            "U2002",
        )

        self.assertEqual("clarify", other_user.path)
        self.assertIn("订单号", other_user.answer)
        self.assertEqual([], self.api.logistics_calls)

    def test_expired_active_order_is_not_reused(self):
        self.workflow.run("DD1001发货了吗？", "expired", "U1001")
        self.memory.get("expired").active_order.updated_at -= 1900

        followup = self.workflow.run(
            "要多久能到啊",
            "expired",
            "U1001",
        )

        self.assertEqual("clarify", followup.path)
        self.assertEqual([], self.api.logistics_calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
