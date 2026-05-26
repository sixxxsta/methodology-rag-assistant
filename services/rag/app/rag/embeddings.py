from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._lock = threading.Lock()

    def _get_model(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            logger.info("Embedding model loaded")
            return self._model

    @property
    def vector_size(self) -> int:
        model = self._get_model()
        return model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [vec.tolist() for vec in vectors]
