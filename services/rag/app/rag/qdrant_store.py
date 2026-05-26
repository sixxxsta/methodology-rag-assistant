from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from .chunker import Chunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source: str
    score: float
    chunk_index: int


class QdrantStore:
    def __init__(
        self,
        *,
        url: str,
        collection: str,
        api_key: str = "",
        vector_size: int,
    ):
        self._collection = collection
        self._vector_size = vector_size
        kwargs: dict[str, Any] = {"url": url}
        if api_key:
            kwargs["api_key"] = api_key
        self._client = QdrantClient(**kwargs)

    @property
    def collection(self) -> str:
        return self._collection

    def ensure_collection(self) -> None:
        exists = self._client.collection_exists(self._collection)
        if exists:
            info = self._client.get_collection(self._collection)
            current_size = info.config.params.vectors.size  # type: ignore[union-attr]
            if current_size != self._vector_size:
                logger.warning(
                    "Collection vector size mismatch (%s != %s), recreating",
                    current_size,
                    self._vector_size,
                )
                self._client.delete_collection(self._collection)
                exists = False

        if not exists:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qmodels.VectorParams(
                    size=self._vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection: %s", self._collection)

    def count(self) -> int:
        if not self._client.collection_exists(self._collection):
            return 0
        return self._client.count(collection_name=self._collection, exact=True).count

    def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")

        points: list[qmodels.PointStruct] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.source}:{chunk.chunk_index}"))
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "text": chunk.text,
                        "source": chunk.source,
                        "chunk_index": chunk.chunk_index,
                    },
                )
            )

        self._client.upsert(collection_name=self._collection, points=points)
        return len(points)

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        hits = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        ).points

        results: list[RetrievedChunk] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                RetrievedChunk(
                    text=str(payload.get("text", "")),
                    source=str(payload.get("source", "unknown")),
                    score=float(hit.score or 0.0),
                    chunk_index=int(payload.get("chunk_index", 0)),
                )
            )
        return results
