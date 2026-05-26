#!/usr/bin/env python3
"""Ingest knowledge base into Qdrant."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.rag.pipeline import RAGPipeline  # noqa: E402


def main() -> None:
    settings = get_settings()
    pipeline = RAGPipeline(settings)
    knowledge_dir = Path(settings.knowledge_dir).resolve()
    stats = pipeline.ingest_directory(knowledge_dir)
    total = pipeline.store.count()
    print(f"Ingested {stats['chunks']} chunks from {stats['files']} files")
    print(f"Collection '{settings.qdrant_collection}' now has {total} points")


if __name__ == "__main__":
    main()
