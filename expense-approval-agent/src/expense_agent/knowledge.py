from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any


def _chinese_tokens(text: str) -> set[str]:
    return {
        char
        for char in text
        if "\u4e00" <= char <= "\u9fff"
    }


class PolicyKnowledgeService:
    """本地制度检索兜底；结果明确标记为 local，不冒充向量检索。"""

    def __init__(self, policy_file: Path):
        self.policy_file = policy_file
        self.sections = self._load(policy_file)

    @staticmethod
    def _load(path: Path) -> list[tuple[str, str]]:
        sections = []
        title = ""
        lines: list[str] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.startswith("## "):
                if title:
                    sections.append(
                        (title, "\n".join(lines).strip())
                    )
                title = raw[3:].strip()
                lines = []
            elif title:
                lines.append(raw)
        if title:
            sections.append((title, "\n".join(lines).strip()))
        return sections

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        tokens = _chinese_tokens(query)
        ranked = sorted(
            self.sections,
            key=lambda item: (
                item[0] in query,
                len(tokens & _chinese_tokens(item[0] + item[1])),
            ),
            reverse=True,
        )
        selected = []
        for title, content in ranked:
            overlap = len(tokens & _chinese_tokens(title + content))
            if overlap < 2 and selected:
                continue
            selected.append(
                {
                    "title": title,
                    "excerpt": content[:220],
                    "retrieval_mode": "local_fallback",
                    "score": None,
                }
            )
            if len(selected) >= top_k:
                break
        return selected


class VectorPolicyKnowledgeService:
    """阿里云 Embedding + Chroma 向量召回，并用制度关键词做轻量重排。"""

    def __init__(
        self,
        policy_file: Path,
        persist_directory: Path,
        embedding_config: dict[str, str],
        *,
        top_k: int = 3,
        score_threshold: float = 1.15,
    ):
        self.policy_file = policy_file
        self.persist_directory = persist_directory
        self.embedding_config = embedding_config
        self.top_k = top_k
        self.score_threshold = score_threshold
        self._vectorstore = None

    def _ensure_ready(self) -> None:
        if self._vectorstore is not None:
            return
        from langchain_chroma import Chroma
        from langchain_core.documents import Document
        from langchain_openai import OpenAIEmbeddings

        text = self.policy_file.read_text(encoding="utf-8")
        local = PolicyKnowledgeService(self.policy_file)
        documents = [
            Document(
                page_content=f"{title}\n{content}",
                metadata={"title": title},
            )
            for title, content in local.sections
        ]
        digest = sha256(text.encode("utf-8")).hexdigest()[:12]
        collection_name = f"expense_policy_cosine_v2_{digest}"
        document_ids = [
            f"policy-section-{index}"
            for index in range(len(documents))
        ]
        embeddings = OpenAIEmbeddings(
            api_key=self.embedding_config["api_key"],
            base_url=self.embedding_config["base_url"],
            model=self.embedding_config["model"],
            chunk_size=10,
            check_embedding_ctx_length=False,
        )
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=str(self.persist_directory),
            collection_name=collection_name,
            collection_metadata={"hnsw:space": "cosine"},
            ids=document_ids,
        )

    @staticmethod
    def _hybrid_rank(
        query: str,
        document: Any,
        vector_distance: float,
    ) -> tuple[float, int, str]:
        content = document.page_content
        title = str(document.metadata.get("title", "未命名制度"))
        overlap = len(
            _chinese_tokens(query)
            & _chinese_tokens(title + content)
        )
        title_bonus = 0.45 if title.replace("规则", "") in query else 0.0
        hybrid_distance = (
            float(vector_distance)
            - min(overlap, 12) * 0.025
            - title_bonus
        )
        return hybrid_distance, overlap, title

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_ready()
        requested = top_k or self.top_k
        candidates = self._vectorstore.similarity_search_with_score(
            query,
            k=max(requested * 3, 8),
        )
        ranked = sorted(
            (
                (
                    *self._hybrid_rank(query, document, score),
                    document,
                    float(score),
                )
                for document, score in candidates
            ),
            key=lambda item: item[0],
        )
        selected = []
        for hybrid_distance, overlap, title, document, vector_distance in ranked:
            if (
                hybrid_distance > self.score_threshold
                and overlap < 2
                and selected
            ):
                continue
            content = document.page_content
            excerpt = content
            if content.startswith(title):
                excerpt = content[len(title) :].strip()
            selected.append(
                {
                    "title": title,
                    "excerpt": excerpt[:220],
                    "retrieval_mode": "vector",
                    "score": round(vector_distance, 4),
                }
            )
            if len(selected) >= requested:
                break
        return selected


class ResilientPolicyKnowledgeService:
    def __init__(self, primary: Any, fallback: Any):
        self.primary = primary
        self.fallback = fallback

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        try:
            result = self.primary.retrieve(query, top_k)
            if result:
                return result
        except Exception:
            pass
        return self.fallback.retrieve(query, top_k)
