from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    source: str
    chunk_index: int


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def chunk_document(
    content: str,
    source: str,
    *,
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:
    parts = split_text(content, chunk_size, overlap)
    return [Chunk(text=part, source=source, chunk_index=i) for i, part in enumerate(parts)]
