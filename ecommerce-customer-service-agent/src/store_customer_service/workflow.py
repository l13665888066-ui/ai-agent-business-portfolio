from __future__ import annotations

from typing import Any

from ecommerce_agent.conversation_workflow import CustomerConversationWorkflow
from ecommerce_agent.models import AgentResponse, Route


class AdaptiveCustomerWorkflow(CustomerConversationWorkflow):
    """业务查询保持确定性，开放式交流交给无 Tool 权限的会话层。"""

    def __init__(self, *args: Any, conversation_responder: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.conversation_responder = conversation_responder

    @staticmethod
    def _smalltalk_answer(question: str) -> None:
        return None

    def _dispatch(
        self,
        route: Route,
        question: str,
        session_id: str,
        user_id: str,
    ) -> AgentResponse:
        if route.need_tool or route.need_human or route.missing_params:
            return super()._dispatch(route, question, session_id, user_id)

        prior_history = self.memory.get(session_id).history[:-1]
        conversation_answer = self.conversation_responder.respond(
            question,
            prior_history,
        )
        if conversation_answer:
            return AgentResponse(
                True,
                "conversation",
                conversation_answer,
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
            "您可以继续说说具体情况，或者告诉我是想咨询订单、物流、库存还是售后问题。",
            route=route,
            details=rag,
            session_id=session_id,
        )
