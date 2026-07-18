from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class KnowledgeService(Protocol):
    def answer(self, question: str) -> dict[str, Any]: ...


class VectorRAGService:
    """延迟初始化，避免导入模块时直接访问外部模型或重建向量库。"""

    def __init__(
        self,
        knowledge_file: Path,
        persist_directory: Path,
        llm_config: dict[str, str],
        embedding_config: dict[str, str],
        top_k: int = 3,
        score_threshold: float = 0.70,
    ):
        self.knowledge_file = knowledge_file
        self.persist_directory = persist_directory
        self.llm_config = llm_config
        self.embedding_config = embedding_config
        self.top_k = top_k
        self.score_threshold = score_threshold
        self._vectorstore = None
        self._chain = None

    @staticmethod
    def _split(text: str) -> list[Any]:
        from langchain_core.documents import Document

        docs = []
        title = None
        lines: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("### "):
                if title and lines:
                    docs.append(
                        Document(
                            page_content="\n".join(lines), metadata={"title": title}
                        )
                    )
                title = line[4:].strip()
                lines = [line]
            elif title:
                lines.append(line)
        if title and lines:
            docs.append(
                Document(page_content="\n".join(lines), metadata={"title": title})
            )
        return docs

    def _ensure_ready(self) -> None:
        if self._vectorstore is not None:
            return
        from langchain_chroma import Chroma
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        docs = self._split(self.knowledge_file.read_text(encoding="utf-8"))
        embeddings = OpenAIEmbeddings(
            api_key=self.embedding_config["api_key"],
            base_url=self.embedding_config["base_url"],
            model=self.embedding_config["model"],
            check_embedding_ctx_length=False,
        )
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._vectorstore = Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            persist_directory=str(self.persist_directory),
            collection_name="ecommerce_knowledge",
        )
        llm = ChatOpenAI(temperature=0, **self.llm_config)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是直播电商客服AI。只能基于可靠知识回答；资料不足时明确说明。
不得编造订单、库存、物流、退款进度，不得承诺一定发货、退款或赔偿。
回复礼貌、简洁并给出下一步。""",
                ),
                ("human", "问题：{question}\n\n可靠知识：\n{context}"),
            ]
        )
        self._chain = prompt | llm | StrOutputParser()

    def answer(self, question: str) -> dict[str, Any]:
        self._ensure_ready()
        results = self._vectorstore.similarity_search_with_score(
            question, k=self.top_k
        )
        reliable = [(doc, score) for doc, score in results if score <= self.score_threshold]
        if not reliable:
            return {
                "matched": False,
                "answer": "抱歉，当前知识库没有与该问题相关的信息。如涉及订单或售后，请提供更具体的信息或联系人工客服。",
                "sources": [],
            }
        context = "\n\n".join(doc.page_content for doc, _ in reliable)
        answer = self._chain.invoke({"question": question, "context": context})
        return {
            "matched": True,
            "answer": answer,
            "sources": [doc.metadata.get("title", "未知标题") for doc, _ in reliable],
        }


class KeywordKnowledgeService:
    """外部Embedding不可用时的安全兜底，不冒充向量检索结果。"""

    def __init__(self, knowledge_file: Path):
        self.sections = self._load(knowledge_file)

    @staticmethod
    def _load(path: Path) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        title = ""
        lines: list[str] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.startswith("### "):
                if title:
                    sections.append((title, "\n".join(lines)))
                title = raw[4:].strip()
                lines = [raw]
            elif title:
                lines.append(raw)
        if title:
            sections.append((title, "\n".join(lines)))
        return sections

    def answer(self, question: str) -> dict[str, Any]:
        tokens = {char for char in question if "\u4e00" <= char <= "\u9fff"}
        ranked = sorted(
            self.sections,
            key=lambda item: len(tokens & set(item[0] + item[1])),
            reverse=True,
        )
        if not ranked or len(tokens & set(ranked[0][0] + ranked[0][1])) < 2:
            return {"matched": False, "answer": "当前知识库未找到可靠答案，建议联系人工客服。", "sources": []}
        title, content = ranked[0]
        return {
            "matched": True,
            "answer": f"根据店铺规则：{content.replace('### ' + title, '').strip()}",
            "sources": [title],
            "fallback_mode": "keyword",
        }
