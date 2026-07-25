from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecommerce_agent.models import Route
from store_customer_service.policy_router import PolicyAwareRouter


class OvereagerRouter:
    def route(self, question):
        return Route(
            True,
            "query_order_tool",
            missing_params=["order_id"],
            reason="错误地把所有发货问题都当作订单查询",
        )


class PolicyAwareRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = PolicyAwareRouter(OvereagerRouter())

    def test_generic_shipping_policy_does_not_require_order_number(self):
        for question in (
            "你们什么时候发货？",
            "付款后多久能发货",
            "正常几天发货呀",
        ):
            with self.subTest(question=question):
                route = self.router.route(question)
                self.assertFalse(route.need_tool)
                self.assertEqual([], route.missing_params)

    def test_specific_order_status_still_uses_tool(self):
        route = self.router.route("我的订单发货了吗？")

        self.assertTrue(route.need_tool)
        self.assertEqual("query_order_tool", route.tool_name)
        self.assertEqual(["order_id"], route.missing_params)

    def test_order_number_stays_on_deterministic_tool_path(self):
        route = self.router.route("DD1001发货了吗？")

        self.assertTrue(route.need_tool)
        self.assertEqual({"order_id": "DD1001"}, route.tool_args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
