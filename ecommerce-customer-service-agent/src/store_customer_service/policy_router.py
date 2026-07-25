from __future__ import annotations

from typing import Any

from ecommerce_agent.models import Route
from ecommerce_agent.router import RuleBasedRouter


class PolicyAwareRouter:
    """先执行高置信业务边界，再让模型处理模糊意图。"""

    SHIPPING_POLICY_MARKERS = (
        "什么时候发货",
        "多久发货",
        "几天发货",
        "发货时间",
        "多长时间发货",
        "下单后多久",
        "付款后多久",
    )
    GENERAL_POLICY_MARKERS = (
        "退换货规则",
        "退货规则",
        "换货规则",
        "售后规则",
        "发票规则",
        "保价规则",
    )

    def __init__(
        self,
        primary: Any | None,
        deterministic: RuleBasedRouter | None = None,
    ):
        self.primary = primary
        self.deterministic = deterministic or RuleBasedRouter()

    def route(self, question: str) -> Route:
        text = question.strip()
        deterministic_route = self.deterministic.route(text)

        if (
            deterministic_route.need_tool
            or deterministic_route.need_human
            or deterministic_route.missing_params
        ):
            deterministic_route.reason = (
                f"高置信业务规则：{deterministic_route.reason}"
            )
            return deterministic_route

        if self._is_generic_policy_question(text):
            return Route(
                False,
                reason="店铺通用规则问题，不需要订单号或实时 Tool",
            )

        if self.primary is not None:
            try:
                return self.primary.route(text)
            except Exception:
                pass

        deterministic_route.reason = (
            f"离线安全兜底：{deterministic_route.reason}"
        )
        return deterministic_route

    @classmethod
    def _is_generic_policy_question(cls, text: str) -> bool:
        markers = cls.SHIPPING_POLICY_MARKERS + cls.GENERAL_POLICY_MARKERS
        if not any(marker in text for marker in markers):
            return False

        realtime_context = (
            "我的订单",
            "我这单",
            "这个订单",
            "订单号",
            "DD",
            "还没发",
            "怎么还不发",
        )
        return not any(marker in text.upper() for marker in realtime_context)
