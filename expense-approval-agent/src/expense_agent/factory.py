from __future__ import annotations

from .config import Settings
from .database import Database
from .extractor import StructuredExtractor
from .knowledge import (
    PolicyKnowledgeService,
    ResilientPolicyKnowledgeService,
    VectorPolicyKnowledgeService,
)
from .policy import ApprovalPolicyEngine
from .semantic_review import (
    LLMPurposeReviewer,
    LocalPurposeReviewer,
    ResilientPurposeReviewer,
)
from .workflow import ExpenseApprovalWorkflow


def create_workflow(
    settings: Settings | None = None,
) -> tuple[ExpenseApprovalWorkflow, Database]:
    settings = settings or Settings.from_env()
    database = Database(settings.database_file)

    local_knowledge = PolicyKnowledgeService(
        settings.policy_file
    )
    vector_ready = all(
        (
            settings.aliyun_api_key,
            settings.aliyun_embedding_base_url,
        )
    )
    if vector_ready:
        vector_knowledge = VectorPolicyKnowledgeService(
            settings.policy_file,
            settings.vector_store_directory,
            {
                "api_key": settings.aliyun_api_key,
                "base_url": settings.aliyun_embedding_base_url,
                "model": settings.embedding_model,
            },
            top_k=settings.rag_top_k,
            score_threshold=settings.rag_score_threshold,
        )
        knowledge = ResilientPolicyKnowledgeService(
            vector_knowledge,
            local_knowledge,
        )
    else:
        knowledge = local_knowledge

    local_reviewer = LocalPurposeReviewer()
    llm_ready = all(
        (
            settings.deepseek_api_key,
            settings.deepseek_base_url,
        )
    )
    if llm_ready:
        reviewer = ResilientPurposeReviewer(
            LLMPurposeReviewer(
                settings.deepseek_api_key,
                settings.deepseek_base_url,
                settings.deepseek_model,
            ),
            local_reviewer,
        )
    else:
        reviewer = local_reviewer

    workflow = ExpenseApprovalWorkflow(
        StructuredExtractor(),
        ApprovalPolicyEngine(),
        knowledge,
        reviewer,
        database,
    )
    return workflow, database
