from __future__ import annotations

import re
from time import perf_counter
from typing import Any

from .audit import NullAuditLogger
from .memory import InMemoryConversationStore
from .models import AgentResponse, Route, ToolResult


ORDER_RE = re.compile(r"(?<![A-Z0-9])DD\d{4}(?!\d)", re.IGNORECASE)
SKU_RE = re.compile(r"(?<![A-Z0-9])[A-Z]+-[A-Z0-9-]{2,}(?![A-Z0-9-])", re.IGNORECASE)


class AgentWorkflow:
    def __init__(
        self,
        router: Any,
        tool_executor: Any,
        knowledge_service: Any,
        memory_store: InMemoryConversationStore | None = None,
        audit_logger: Any | None = None,
    ):
        self.router = router
        self.tool_executor = tool_executor
        self.knowledge_service = knowledge_service
        self.memory = memory_store or InMemoryConversationStore()
        self.audit = audit_logger or NullAuditLogger()

    def run(self, question: str, session_id: str, user_id: str) -> AgentResponse:
        started = perf_counter()
        question = (question or "").strip()
        if not question:
            return AgentResponse(False, "invalid_input", "请输入需要咨询的问题。", "EMPTY_QUESTION", session_id=session_id)

        self.memory.append(session_id, "user", question)
        try:
            route = self._resume_pending(question, session_id) or self.router.route(question)
            response = self._dispatch(route, question, session_id, user_id)
        except Exception as error:
            response = AgentResponse(
                False,
                "system_fallback",
                "系统暂时无法完成处理，请稍后重试或联系人工客服。",
                "WORKFLOW_ERROR",
                details={"error_type": type(error).__name__},
                session_id=session_id,
            )

        self.memory.append(session_id, "assistant", response.answer)
        self.audit.write(
            {
                "session_id": session_id,
                "user_id": user_id,
                "question": question[:200],
                "path": response.path,
                "success": response.success,
                "error_code": response.error_code,
                "route": response.route.to_dict() if response.route else None,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            }
        )
        return response

    def _resume_pending(self, question: str, session_id: str) -> Route | None:
        pending = self.memory.get(session_id).pending
        if pending is None:
            return None
        args = dict(pending.collected_args)
        missing = list(pending.missing_params)
        if "order_id" in missing:
            match = ORDER_RE.search(question)
            if match:
                args["order_id"] = match.group(0).upper()
                missing.remove("order_id")
        if "sku" in missing:
            match = SKU_RE.search(question)
            if match:
                args["sku"] = match.group(0).upper()
                missing.remove("sku")
        if missing:
            return Route(
                True,
                pending.tool_name,
                args,
                missing_params=missing,
                reason="继续等待上一轮缺失参数",
            )
        return Route(
            True,
            pending.tool_name,
            args,
            reason="已从多轮上下文补齐参数",
        )

    def _dispatch(
        self, route: Route, question: str, session_id: str, user_id: str
    ) -> AgentResponse:
        route.validate()
        if route.need_human:
            self.memory.clear_pending(session_id)
            return AgentResponse(
                True,
                "human",
                "这个问题存在投诉或高风险情况，已建议转人工客服进一步处理。",
                route=route,
                session_id=session_id,
            )
        if route.missing_params:
            self.memory.set_pending(
                session_id,
                route.tool_name,
                route.missing_params,
                route.tool_args,
            )
            labels = {"order_id": "订单号（如DD1001）", "sku": "商品SKU"}
            fields = "、".join(labels.get(item, item) for item in route.missing_params)
            return AgentResponse(
                True,
                "clarify",
                f"为了继续查询，请提供{fields}。",
                route=route,
                session_id=session_id,
            )
        if route.need_tool:
            self.memory.clear_pending(session_id)
            result: ToolResult = self.tool_executor.execute(route, user_id)
            return AgentResponse(
                result.success,
                "tool",
                self._format_tool_answer(route.tool_name, result),
                result.error_code,
                route,
                result.to_dict(),
                session_id,
            )

        rag = self.knowledge_service.answer(question)
        path = "rag" if rag.get("matched") else "rag_fallback"
        return AgentResponse(
            True,
            path,
            rag["answer"],
            route=route,
            details=rag,
            session_id=session_id,
        )

    @staticmethod
    def _format_tool_answer(tool_name: str, result: ToolResult) -> str:
        if not result.success:
            mapping = {
                "ORDER_NOT_FOUND": "暂未查到该订单，请核对订单号后重试。",
                "ACCESS_DENIED": "该订单不属于当前用户，无法查看相关信息。",
                "API_TIMEOUT": "业务系统响应超时，请稍后重试。",
                "API_CONNECTION_ERROR": "业务系统暂时不可用，请稍后重试。",
            }
            return mapping.get(result.error_code, result.message or "本次查询未成功。")
        data = result.data or {}
        if tool_name == "query_order_tool":
            return f"订单{data['order_id']}当前状态为：{data['order_status']}，支付状态：{data['pay_status']}。"
        if tool_name == "query_logistics_tool":
            return f"订单{data['order_id']}由{data['company']}承运，当前{data['logistics_status']}；最新进度：{data['latest_trace']}。"
        if tool_name == "query_inventory_tool":
            return f"商品{data['sku']}当前可用库存为{data['available_stock']}件。"
        if tool_name == "query_refund_tool":
            return f"订单{data['order_id']}退款状态为：{data['refund_status']}。"
        return result.message
