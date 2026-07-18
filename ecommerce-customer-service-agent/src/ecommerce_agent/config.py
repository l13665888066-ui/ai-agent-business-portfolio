from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str | None
    deepseek_base_url: str | None
    deepseek_model: str
    aliyun_api_key: str | None
    aliyun_embedding_base_url: str | None
    embedding_model: str
    business_api_url: str
    business_api_token: str
    knowledge_file: Path
    vector_store_dir: Path
    audit_log_file: Path
    rag_score_threshold: float
    rag_top_k: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            aliyun_api_key=os.getenv("ALIYUN_API_KEY"),
            aliyun_embedding_base_url=(
                os.getenv("ALIYUN_EMBEDDING_BASE_URL")
                or os.getenv("ALIYUN_BASE_URL")
            ),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
            business_api_url=os.getenv(
                "BUSINESS_API_URL", "http://127.0.0.1:8765"
            ).rstrip("/"),
            business_api_token=os.getenv("BUSINESS_API_TOKEN", "demo-token"),
            knowledge_file=PROJECT_ROOT / "data" / "ecommerce_knowledge_base.txt",
            vector_store_dir=PROJECT_ROOT / ".runtime" / "chroma",
            audit_log_file=PROJECT_ROOT / ".runtime" / "audit.jsonl",
            rag_score_threshold=float(os.getenv("RAG_SCORE_THRESHOLD", "0.70")),
            rag_top_k=int(os.getenv("RAG_TOP_K", "3")),
        )
