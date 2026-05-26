"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { fetchHealth, sendChat } from "@/lib/api";
import type { ChatMessage, HealthInfo } from "@/lib/types";
import { ChatMessageBubble, TypingIndicator } from "./chat-message";
import { Sidebar } from "./sidebar";
import clsx from "clsx";

const SESSION_KEY = "methodology_session_id";
const WELCOME: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Привет! Я методологический ассистент. Спросите о планировании спринта, ролях в команде, Kanban, DevOps или документации по ГОСТ.",
};

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollDown = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    setSessionId(localStorage.getItem(SESSION_KEY) || "");
  }, []);

  useEffect(() => {
    scrollDown();
  }, [messages, loading, scrollDown]);

  useEffect(() => {
    async function poll() {
      try {
        setHealth(await fetchHealth());
      } catch {
        setHealth(null);
      }
    }
    poll();
    const id = setInterval(poll, 30_000);
    return () => clearInterval(id);
  }, []);

  function resizeTextarea() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    resizeTextarea();
    setLastQuestion(text);
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "user", content: text }]);
    setLoading(true);

    try {
      const data = await sendChat(text, sessionId);
      setSessionId(data.session_id);
      localStorage.setItem(SESSION_KEY, data.session_id);
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.answer,
          sources: data.sources,
        },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            err instanceof Error
              ? err.message
              : "Не удалось связаться с сервером. Проверьте, что RAG и Qdrant запущены.",
        },
      ]);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function newChat() {
    setSessionId("");
    localStorage.removeItem(SESSION_KEY);
    setMessages([
      WELCOME,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Новый диалог. Задайте вопрос по методологии проекта.",
      },
    ]);
  }

  const online = health?.status === "ok";
  const llm = health?.llm_provider_active || "—";
  const points = health?.knowledge_points ?? 0;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar onNewChat={newChat} className="hidden md:flex" />

      <main className="flex flex-1 flex-col min-h-0">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3 glass">
          <span
            className={clsx("h-2 w-2 rounded-full", online ? "bg-success" : "bg-muted")}
          />
          <span className="text-sm text-muted">
            {online
              ? `Онлайн · LLM: ${llm} · ${points} фрагментов`
              : "RAG загружается… чат может быть недоступен 1–3 мин"}
          </span>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((msg, i) => {
              const prevUser =
                msg.role === "assistant"
                  ? [...messages].slice(0, i).reverse().find((m) => m.role === "user")?.content
                  : undefined;
              return (
                <ChatMessageBubble
                  key={msg.id}
                  message={msg}
                  sessionId={sessionId}
                  lastQuestion={prevUser}
                />
              );
            })}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        </div>

        <footer className="border-t border-border p-4 glass">
          <form
            onSubmit={handleSubmit}
            className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-border bg-surface p-2 pl-4"
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                resizeTextarea();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              rows={1}
              placeholder="Например: как провести ретроспективу?"
              maxLength={4000}
              className="max-h-36 min-h-[44px] flex-1 resize-none bg-transparent py-2.5 text-sm outline-none placeholder:text-muted"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent text-white transition hover:opacity-90 disabled:opacity-40"
              aria-label="Отправить"
            >
              <Send className="h-5 w-5" />
            </button>
          </form>
          <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-muted">
            RAG: Qdrant → LLM (GigaChat / локальный inference)
          </p>
        </footer>
      </main>

      <div className="border-t border-border p-3 md:hidden">
        <Sidebar onNewChat={newChat} className="!min-h-0 !w-full !border-0 !p-0" />
      </div>
    </div>
  );
}
