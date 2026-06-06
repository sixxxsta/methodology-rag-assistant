"use client";

import { useState } from "react";
import clsx from "clsx";
import type { ChatMessage as Msg, Source } from "@/lib/types";
import { sendFeedback } from "@/lib/api";

type Props = {
  message: Msg;
  sessionId: string;
  lastQuestion?: string;
};

function Sources({ sources }: { sources: Source[] }) {
  return (
    <div className="mt-3 rounded-xl border border-border bg-surface p-3 text-xs">
      <p className="mb-2 font-medium uppercase tracking-wide text-muted">Источники</p>
      <div className="space-y-2">
        {sources.map((s, i) => (
          <div key={`${s.source}-${i}`} className="border-t border-border pt-2 first:border-0 first:pt-0">
            <p className="font-mono text-accent">
              [{i + 1}] {s.source}{" "}
              <span className="text-muted">({Math.round(s.score * 100)}%)</span>
            </p>
            <p className="mt-1 text-muted leading-relaxed">{s.excerpt}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Feedback({
  sessionId,
  question,
  answer,
}: {
  sessionId: string;
  question: string;
  answer: string;
}) {
  const [rated, setRated] = useState<number | null>(null);

  async function rate(n: number) {
    setRated(n);
    try {
      await sendFeedback({ session_id: sessionId, rating: n, question, answer });
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
      <span>Оцените ответ:</span>
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => rate(n)}
            className={clsx(
              "text-lg transition hover:scale-110",
              rated !== null && n <= rated ? "text-amber-400" : "text-muted/40",
            )}
            aria-label={`Оценка ${n}`}
          >
            ★
          </button>
        ))}
      </div>
    </div>
  );
}

export function ChatMessageBubble({ message, sessionId, lastQuestion }: Props) {
  const isUser = message.role === "user";

  return (
    <article
      className={clsx("flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300", isUser && "flex-row-reverse")}
    >
      <div
        className={clsx(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border text-xs font-semibold",
          isUser ? "bg-accent/15 text-accent" : "bg-surface-2 text-accent",
        )}
      >
        {isUser ? "Вы" : "M"}
      </div>
      <div className={clsx("max-w-[85%] min-w-0", isUser && "text-right")}>
        <div
          className={clsx(
            "inline-block rounded-2xl px-4 py-3 text-left text-sm leading-relaxed whitespace-pre-wrap",
            isUser
              ? "border border-accent/30 bg-chat-user text-text"
              : "glass shadow-lg shadow-accent/5",
          )}
        >
          {message.content}
        </div>
        {!isUser && message.sources && message.sources.length > 0 && (
          <>
            <Sources sources={message.sources} />
            {lastQuestion && (
              <Feedback sessionId={sessionId} question={lastQuestion} answer={message.content} />
            )}
          </>
        )}
      </div>
    </article>
  );
}

export function TypingIndicator() {
  return (
    <article className="flex gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface-2 text-xs font-semibold text-accent">
        M
      </div>
      <div className="glass flex gap-1 rounded-2xl border border-border px-4 py-4">
        <span className="h-2 w-2 animate-bounce rounded-full bg-accent/60 [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-accent/60 [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-accent/60 [animation-delay:300ms]" />
      </div>
    </article>
  );
}
