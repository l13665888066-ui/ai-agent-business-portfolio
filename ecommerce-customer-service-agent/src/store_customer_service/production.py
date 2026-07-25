from __future__ import annotations

from ecommerce_agent.api_client import BusinessAPIClient
from ecommerce_agent.audit import AuditLogger
from ecommerce_agent.config import Settings
from ecommerce_agent.memory import InMemoryConversationStore
from ecommerce_agent.rag import KeywordKnowledgeService, VectorRAGService
from ecommerce_agent.router import LLMRouter, RuleBasedRouter
from ecommerce_agent.tools import SafeToolExecutor

from .knowledge import ResilientKnowledgeService
from .knowledge_output import CustomerFriendlyKnowledgeService
from .policy_router import PolicyAwareRouter
from .responder import LLMConversationResponder
from .safe_responder import SafeConversationResponder
from .workflow import AdaptiveCustomerWorkflow


def create_customer_service(
    settings: Settings | None = None,
) -> AdaptiveCustomerWorkflow:
    settings = settings or Settings.from_env()

    llm_router = None
    llm_conversation = None
    if settings.deepseek_api_key and settings.deepseek_base_url:
        llm_router = LLMRouter(
            settings.deepseek_api_key,
            settings.deepseek_base_url,
            settings.deepseek_model,
        )
        llm_conversation = LLMConversationResponder(
            settings.deepseek_api_key,
            settings.deepseek_base_url,
            settings.deepseek_model,
        )

    local_knowledge = CustomerFriendlyKnowledgeService(
        KeywordKnowledgeService(settings.knowledge_file)
    )
    vector_ready = all(
        (
            settings.deepseek_api_key,
            settings.deepseek_base_url,
            settings.aliyun_api_key,
            settings.aliyun_embedding_base_url,
        )
    )
    if vector_ready:
        vector_knowledge = VectorRAGService(
            settings.knowledge_file,
            settings.vector_store_dir,
            {
                "api_key": settings.deepseek_api_key,
                "base_url": settings.deepseek_base_url,
                "model": settings.deepseek_model,
            },
            {
                "api_key": settings.aliyun_api_key,
                "base_url": settings.aliyun_embedding_base_url,
                "model": settings.embedding_model,
            },
            settings.rag_top_k,
            settings.rag_score_threshold,
        )
        knowledge_service = ResilientKnowledgeService(
            vector_knowledge,
            local_knowledge,
        )
    else:
        knowledge_service = local_knowledge

    return AdaptiveCustomerWorkflow(
        router=PolicyAwareRouter(llm_router, RuleBasedRouter()),
        tool_executor=SafeToolExecutor(
            BusinessAPIClient(
                settings.business_api_url,
                settings.business_api_token,
            )
        ),
        knowledge_service=knowledge_service,
        memory_store=InMemoryConversationStore(),
        audit_logger=AuditLogger(settings.audit_log_file),
        conversation_responder=SafeConversationResponder(llm_conversation),
    )
