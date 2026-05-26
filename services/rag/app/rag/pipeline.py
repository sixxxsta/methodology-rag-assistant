from __future__ import annotations

import logging
from pathlib import Path

from ..config import Settings
from ..llm.base import LLMProvider
from ..llm.factory import build_llm
from ..sessions import ChatSessionStore
from .chunker import chunk_document
from .embeddings import EmbeddingService
from .qdrant_store import QdrantStore, RetrievedChunk

logger = logging.getLogger(__name__)


class RAGPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.embeddings = EmbeddingService(settings.embedding_model)
        self.store = QdrantStore(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            api_key=settings.qdrant_api_key,
            vector_size=self.embeddings.vector_size,
        )
        self.llm, self.llm_provider_active = build_llm(settings)
        self.sessions = ChatSessionStore(max_messages=20)
        logger.info("RAG pipeline ready, LLM provider: %s", self.llm_provider_active)

    def ensure_ready(self) -> None:
        self.store.ensure_collection()

    def ingest_directory(self, directory: Path) -> dict[str, int]:
        self.ensure_ready()
        if not directory.exists():
            raise FileNotFoundError(f"knowledge directory not found: {directory}")

        total_chunks = 0
        files = sorted(directory.rglob("*.md")) + sorted(directory.rglob("*.txt"))
        for file_path in files:
            content = file_path.read_text(encoding="utf-8")
            source = str(file_path.relative_to(directory)).replace("\\", "/")
            chunks = chunk_document(
                content,
                source,
                chunk_size=self.settings.chunk_size,
                overlap=self.settings.chunk_overlap,
            )
            if not chunks:
                continue
            vectors = self.embeddings.encode(
                [c.text for c in chunks],
                batch_size=self.settings.embedding_batch_size,
            )
            inserted = self.store.upsert_chunks(chunks, vectors)
            total_chunks += inserted
            logger.info("Ingested %s chunks from %s", inserted, source)

        return {"files": len(files), "chunks": total_chunks}

    def _retrieve(self, query: str) -> list[RetrievedChunk]:
        query_vector = self.embeddings.encode([query], batch_size=1)[0]
        return self.store.search(
            query_vector,
            top_k=self.settings.rag_top_k,
            score_threshold=self.settings.rag_score_threshold,
        )

    @staticmethod
    def _format_context(chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return ""
        blocks: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            blocks.append(
                f"[{i}] Источник: {chunk.source} (релевантность: {chunk.score:.2f})\n{chunk.text}"
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _build_user_prompt(question: str, context: str, history: str) -> str:
        parts: list[str] = []
        if history:
            parts.append(f"История диалога:\n{history}")
        if context:
            parts.append(f"Контекст из базы знаний:\n{context}")
        parts.append(f"Вопрос студента:\n{question}")
        parts.append(
            "Дай структурированный практичный ответ. "
            "Если используешь факты из контекста — укажи номера источников в квадратных скобках."
        )
        return "\n\n".join(parts)

    @staticmethod
    def _fallback_answer_from_context(
        question: str, chunks: list[RetrievedChunk]
    ) -> str:
        if not chunks:
            return (
                "Сервис генерации ответа (inference) сейчас недоступен, "
                "и в базе знаний нет подходящих фрагментов по вашему вопросу.\n\n"
                "Запустите LLM:\n"
                "`docker compose --profile gpu up -d inference`\n\n"
                "Дождитесь готовности (первый запуск может занять 10–20 минут), "
                "затем повторите вопрос."
            )
        parts = [
            "⚠️ Модель генерации временно недоступна (inference не запущен или ещё загружается). "
            "Ниже — релевантные фрагменты из базы знаний по вашему вопросу:\n",
        ]
        for i, chunk in enumerate(chunks[:4], start=1):
            parts.append(
                f"\n### [{i}] {chunk.source}\n{chunk.text.strip()}"
            )
        parts.append(
            "\n\n---\nЧтобы получить связный ответ от нейросети, выполните в папке проекта:\n"
            "`docker compose --profile gpu up -d inference`"
        )
        return "\n".join(parts)

    async def chat(
        self,
        message: str,
        *,
        session_id: str | None = None,
        language: str | None = None,
    ) -> dict:
        message = message.strip()
        if not message:
            raise ValueError("message must not be empty")

        session = self.sessions.get_or_create(session_id)
        retrieved = self._retrieve(message)
        context = self._format_context(retrieved)
        history = session.format_history()
        user_prompt = self._build_user_prompt(message, context, history)

        llm_context = self.settings.system_prompt
        if context:
            llm_context = f"{llm_context}\n\n{context}"

        try:
            answer = await self.llm.generate(
                user_prompt,
                context=llm_context,
                language=language or self.settings.response_language,
            )
        except Exception as exc:
            logger.warning("LLM generate failed (%s), using knowledge fallback", exc)
            answer = self._fallback_answer_from_context(message, retrieved)

        session.add("user", message)
        session.add("assistant", answer)

        return {
            "session_id": session.session_id,
            "answer": answer,
            "sources": [
                {
                    "source": c.source,
                    "score": round(c.score, 4),
                    "chunk_index": c.chunk_index,
                    "excerpt": c.text[:280] + ("…" if len(c.text) > 280 else ""),
                }
                for c in retrieved
            ],
        }
