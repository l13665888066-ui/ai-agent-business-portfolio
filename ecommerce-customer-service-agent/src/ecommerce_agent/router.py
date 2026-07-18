from __future__ import annotations

import json
import re
from typing import Protocol

from .models import Route


class Router(Protocol):
    def route(self, question: str) -> Route: ...


class RuleBasedRouter:
    """离线兜底路由，保证模型异常时仍能安全降级。"""

    ORDER_RE = re.compile(r"(?<![A-Z0-9])DD\d{4}(?!\d)", re.IGNORECASE)
    SKU_RE = re.compile(r"(?<![A-Z0-9])[A-Z]+-[A-Z0-9-]{2,}(?![A-Z0-9-])", re.IGNORECASE)

    def route(self, question: str) -> Route:
        text = question.strip()
        if any(word in text for word in ("投诉", "差评", "平台举报", "人工客服")):
            return Route(False, need_human=True, reason="命中投诉或人工处理规则")

        order_match = self.ORDER_RE.search(text)
        order_id = order_match.group(0).upper() if order_match else None

        if any(word in text for word in ("物流", "快递", "到哪", "运输")):
            return self._order_route("query_logistics_tool", order_id, "物流实时查询")
        if any(word in text for word in ("退款进度", "退款到账", "退钱")):
            return self._order_route("query_refund_tool", order_id, "退款实时查询")
        if any(word in text for word in ("订单状态", "发货了吗", "是否发货")):
            return self._order_route("query_order_tool", order_id, "订单实时查询")
        if any(word in text for word in ("库存", "有货", "缺货")):
            sku_match = self.SKU_RE.search(text)
            if sku_match:
                return Route(
                    True,
                    "query_inventory_tool",
                    {"sku": sku_match.group(0).upper()},
                    reason="库存实时查询",
                )
            return Route(
                True,
                "query_inventory_tool",
                missing_params=["sku"],
                reason="库存查询缺少SKU",
            )
        return Route(False, reason="固定规则或知识库范围问题")

    @staticmethod
    def _order_route(tool_name: str, order_id: str | None, reason: str) -> Route:
        if order_id:
            return Route(True, tool_name, {"order_id": order_id}, reason=reason)
        return Route(
            True,
            tool_name,
            missing_params=["order_id"],
            reason=f"{reason}缺少订单号",
        )


class LLMRouter:
    def __init__(self, api_key: str, base_url: str, model: str):
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
你是直播电商客服Agent的路由器，只做路径选择，不直接回答。

可用工具：
- query_order_tool：订单状态，需要order_id。
- query_logistics_tool：物流进度，需要order_id。
- query_inventory_tool：实时库存，需要sku。
- query_refund_tool：退款进度，需要order_id。

规则：
1. 投诉、差评、举报、明确要求人工时，need_human=true。
2. 缺少工具参数时保留need_tool=true，在missing_params中列出缺失字段。
3. 店铺规则、退换货政策、活动说明等交给RAG。
4. 无关问题也交给RAG做知识范围兜底。
5. 不得编造参数，不得输出白名单以外的工具。

只输出JSON：
{{
  "need_tool": true,
  "tool_name": "query_order_tool/query_logistics_tool/query_inventory_tool/query_refund_tool/none",
  "tool_args": {{}},
  "missing_params": [],
  "need_human": false,
  "reason": ""
}}
""",
                ),
                ("human", "用户问题：{question}"),
            ]
        )
        self.chain = prompt | llm | JsonOutputParser()

    def route(self, question: str) -> Route:
        value = self.chain.invoke({"question": question})
        if isinstance(value, str):
            value = json.loads(value)
        return Route.from_mapping(value)


class HybridRouter:
    def __init__(self, primary: Router | None, fallback: Router | None = None):
        self.primary = primary
        self.fallback = fallback or RuleBasedRouter()

    def route(self, question: str) -> Route:
        if self.primary is not None:
            try:
                return self.primary.route(question)
            except Exception:
                pass
        route = self.fallback.route(question)
        route.reason = f"离线安全兜底：{route.reason}"
        return route
