from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    session_id: str
    rating: int
    comment: str = ""
    question: str = ""
    answer: str = ""
    created_at: float = field(default_factory=time.time)


class FeedbackStore:
    def __init__(self, path: Path | None = None):
        self._path = path or Path("data/feedback.jsonl")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def add(self, entry: FeedbackEntry) -> None:
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        logger.info("Feedback saved: session=%s rating=%s", entry.session_id, entry.rating)
