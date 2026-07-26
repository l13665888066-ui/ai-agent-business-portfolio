from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_file: Path
    policy_file: Path
    upload_directory: Path
    vector_store_directory: Path
    deepseek_api_key: str | None
    deepseek_base_url: str | None
    deepseek_model: str
    aliyun_api_key: str | None
    aliyun_embedding_base_url: str | None
    embedding_model: str
    rag_score_threshold: float
    rag_top_k: int
    web_host: str
    web_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        return cls(
            database_file=PROJECT_ROOT
            / ".runtime"
            / "expense_approval_v2.db",
            policy_file=PROJECT_ROOT
            / "data"
            / "expense_policy.md",
            upload_directory=PROJECT_ROOT
            / ".runtime"
            / "uploads",
            vector_store_directory=PROJECT_ROOT
            / ".runtime"
            / "policy_chroma",
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL"),
            deepseek_model=os.getenv(
                "DEEPSEEK_MODEL",
                "deepseek-v4-flash",
            ),
            aliyun_api_key=os.getenv("ALIYUN_API_KEY"),
            aliyun_embedding_base_url=(
                os.getenv("ALIYUN_EMBEDDING_BASE_URL")
                or os.getenv("ALIYUN_BASE_URL")
            ),
            embedding_model=os.getenv(
                "EMBEDDING_MODEL",
                "text-embedding-v4",
            ),
            rag_score_threshold=float(
                os.getenv(
                    "EXPENSE_RAG_SCORE_THRESHOLD",
                    "0.78",
                )
            ),
            rag_top_k=int(
                os.getenv("EXPENSE_RAG_TOP_K", "3")
            ),
            web_host=os.getenv("WEB_HOST", "127.0.0.1"),
            web_port=int(os.getenv("WEB_PORT", "5100")),
        )
