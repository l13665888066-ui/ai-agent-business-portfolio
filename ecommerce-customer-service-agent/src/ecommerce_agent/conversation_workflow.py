from __future__ import annotations

import re
from typing import Any

from .models import AgentResponse, Route, ToolResult
from .workflow import AgentWorkflow


ORDER_ONLY_RE = re.compile(
    r"^(?:订单号(?:是|为)?|换成|改成|查一下)?\s*(DD\d{4})\s*[。！!？?]?$",
    re.IGNORECASE,
)
SKU_ONLY_RE = re.compile(
    r"^(?:SKU(?:是|为)?|换成|改成|查一下)?\s*([A-Z][A-Z0-9-]{2,39})\s*[。！!？?]?$",
    re.IGNORECASE,
)


class CustomerConversationWorkflow(AgentWorkflow):
    """面向真实客服会话的工作流：保留任务上下文，并隐藏内部技术措辞。"""

    RETRYABLE_ORDER_ERRORS = {
        "ACCESS_DENIED",
        "ORDER_NOT_FOUND",
        "INVALID_ORDER_ID",
    }

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._last_tool_by_session: dict[str, str] = {}

    def _resume_pending(self, question: str, session_id: str) -> Route | None:
        pending_route = super()._resume_pending(question, session_id)
        if pending_route is not None:
            return pending_route

        last_tool = self._last_tool_by_session.get(session_id)
        if last_tool in {
            "query_order_tool",
            "query_logistics_tool",
            "query_refund_tool",
        }:
            match = ORDER_ONLY_RE.fullmatch(question.strip())
            if match:
                return Route(
                    True,
                    last_tool,
                    {"order_id": match.group(1).upper()},
                    reason="沿用上一轮订单查询意图",
                )

        if last_tool == "query_inventory_tool":
            match = SKU_ONLY_RE.fullmatch(question.strip())
            if match:
                return Route(
                    True,
                    last_tool,
                    {"sku": match.group(1).upper()},
                    reason="沿用上一轮库存查询意图",
                )
        return None

    def _dispatch(
        self,
        route: Route,
        question: str,
        session_id: str,
        user_id: str,
    ) -> AgentResponse:
        route.validate()

        if route.need_human or route.missing_params:
            return super()._dispatch(route, question, session_id, user_id)

        if route.need_tool:
            result: ToolResult = self.tool_executor.execute(route, user_id)
            self._last_tool_by_session[session_id] = route.tool_name

            if result.success:
                self.memory.clear_pending(session_id)
            elif result.error_code in self.RETRYABLE_ORDER_ERRORS:
                self.memory.set_pending(
                    session_id,
                    route.tool_name,
                    ["order_id"],
                )
            else:
                self.memory.clear_pending(session_id)

            return AgentResponse(
                result.success,
                "tool",
                self._format_customer_tool_answer(route, result),
                result.error_code,
                route,
                result.to_dict(),
                session_id,
            )

        smalltalk = self._smalltalk_answer(question)
        if smalltalk:
            return AgentResponse(
                True,
                "smalltalk",
                smalltalk,
                route=route,
                session_id=session_id,
            )

        rag = self.knowledge_service.answer(question)
        if rag.get("matched"):
            return AgentResponse(
                True,
                "rag",
                rag["answer"],
                route=route,
                details=rag,
                session_id=session_id,
            )

        return AgentResponse(
            True,
            "guidance",
            "这个问题我暂时无法直接判断。您可以告诉我是订单、物流、库存、退款还是退换货问题；如需人工客服，也可以直接告诉我。",
            route=route,
            details=rag,
            session_id=session_id,
        )

    @staticmethod
    def _smalltalk_answer(question: str) -> str | None:
        text = re.sub(r"[\s，。！!？?～~]+", "", question).lower()
        if text in {"你好", "您好", "在吗", "嗨", "哈喽", "hello", "hi"}:
            return "您好，在的。请问您想咨询订单、物流、库存还是售后问题？"
        if text in {"早上好", "上午好"}:
            return "早上好，请问有什么可以帮您？"
        if text in {"下午好", "晚上好"}:
            return f"{text}，请问有什么可以帮您？"
        if text in {"谢谢", "感谢", "谢谢你", "好的谢谢"}:
            return "不客气。如果还有订单或售后问题，可以继续告诉我。"
        if text in {"再见", "拜拜", "没有了", "没问题了"}:
            return "好的，感谢您的咨询，祝您生活愉快。"
        if any(item in text for item in ("你能做什么", "可以咨询什么", "能帮我什么")):
            return "我可以协助查询订单状态、物流进度、商品库存和退款进度，也可以解答发货、退换货等店铺规则问题。"
        return None

    @classmethod
    def _format_customer_tool_answer(
        cls,
        route: Route,
        result: ToolResult,
    ) -> str:
        if result.success:
            return cls._format_tool_answer(route.tool_name, result)

        order_id = str(route.tool_args.get("order_id", "")).upper()
        mapping = {
            "ACCESS_DENIED": "这个订单不属于当前账号。请重新提供您本人的订单号，我继续帮您查询。",
            "ORDER_NOT_FOUND": f"暂未查到订单{order_id}。请核对订单号后重新发送，我会继续为您查询。",
            "INVALID_ORDER_ID": "订单号格式似乎不正确，请重新提供以DD开头的6位订单号。",
            "API_TIMEOUT": "订单系统响应较慢，请稍后再试；如果比较着急，也可以转人工客服。",
            "API_CONNECTION_ERROR": "订单系统暂时无法连接，请稍后重试或联系人工客服。",
        }
        return mapping.get(result.error_code, result.message or "本次查询没有成功，请稍后重试。")
