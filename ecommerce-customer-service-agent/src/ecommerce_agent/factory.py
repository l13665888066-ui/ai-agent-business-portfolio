from __future__ import annotations

from .api_client import BusinessAPIClient
from .audit import AuditLogger
from .config import Settings
from .memory import InMemoryConversationStore
from .rag import KeywordKnowledgeService, VectorRAGService
from .router import HybridRouter, LLMRouter, RuleBasedRouter
from .tools import SafeToolExecutor
from .workflow import AgentWorkflow


def create_workflow(settings: Settings | None = None) -> AgentWorkflow:
    settings = settings or Settings.from_env()

    primary_router = None
    if settings.deepseek_api_key and settings.deepseek_base_url:
        primary_router = LLMRouter(
            settings.deepseek_api_key,
            settings.deepseek_base_url,
            settings.deepseek_model,
        )
    router = HybridRouter(primary_router, RuleBasedRouter())

    vector_ready = all(
        [
            settings.deepseek_api_key,
            settings.deepseek_base_url,
            settings.aliyun_api_key,
            settings.aliyun_embedding_base_url,
        ]
    )
    if vector_ready:
        knowledge_service = VectorRAGService(
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
    else:
        knowledge_service = KeywordKnowledgeService(settings.knowledge_file)

    api_client = BusinessAPIClient(
        settings.business_api_url,
        settings.business_api_token,
    )
    return AgentWorkflow(
        router=router,
        tool_executor=SafeToolExecutor(api_client),
        knowledge_service=knowledge_service,
        memory_store=InMemoryConversationStore(),
        audit_logger=AuditLogger(settings.audit_log_file),
    )
