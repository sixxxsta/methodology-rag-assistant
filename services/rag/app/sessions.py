from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str
    content: str
    created_at: float = field(default_factory=time.time)


@dataclass
class ChatSession:
    session_id: str
    messages: list[ChatMessage] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content.strip()))

    def format_history(self, max_messages: int = 8) -> str:
        recent = self.messages[-max_messages:]
        lines: list[str] = []
        for msg in recent:
            label = "Студент" if msg.role == "user" else "Ментор"
            lines.append(f"{label}: {msg.content}")
        return "\n".join(lines)


class ChatSessionStore:
    def __init__(self, max_messages: int = 20, ttl_seconds: int = 86_400):
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        self._max_messages = max_messages
        self._ttl_seconds = ttl_seconds

    def _cleanup(self) -> None:
        now = time.time()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if session.messages
            and now - session.messages[-1].created_at > self._ttl_seconds
        ]
        for sid in expired:
            self._sessions.pop(sid, None)

    def get_or_create(self, session_id: str | None) -> ChatSession:
        with self._lock:
            self._cleanup()
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]
            new_id = session_id or str(uuid.uuid4())
            session = ChatSession(session_id=new_id)
            self._sessions[new_id] = session
            return session
