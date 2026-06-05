"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { CycleBanner } from "@/components/cycle-banner";
import { CuratorGuard } from "@/components/curator-guard";
import { Sidebar } from "@/components/sidebar";
import {
  approveCommunication,
  completeCommsPhase,
  downloadPresentationPdf,
  exportQloraDataset,
  fetchMemoryStats,
  syncStrategyMemory,
  fetchCommunicationVersions,
  fetchCommsShortlist,
  fetchFaq,
  generateFaq,
  generateLetter,
  generateLettersBatch,
} from "@/lib/api";
import { canUseEdAgent, getUser } from "@/lib/auth";
import { useActiveCycleId } from "@/lib/use-cycle";
import type { CommunicationInfo, ShortlistCommItem } from "@/lib/types";
import clsx from "clsx";
import { ArrowLeft, Loader2, Mail, Send } from "lucide-react";

export default function CommunicationsPage() {
  const [items, setItems] = useState<ShortlistCommItem[]>([]);
  const [faq, setFaq] = useState<CommunicationInfo | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState("");
  const [memory, setMemory] = useState<Awaited<ReturnType<typeof fetchMemoryStats>> | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [versions, setVersions] = useState<Record<number, Awaited<ReturnType<typeof fetchCommunicationVersions>>["versions"]>>({});
  const canEdit = canUseEdAgent(getUser());
  const cycleId = useActiveCycleId();

  const load = useCallback(async () => {
    setError("");
    try {
      const [data, faqData, mem] = await Promise.all([
        fetchCommsShortlist(),
        fetchFaq(),
        fetchMemoryStats().catch(() => null),
      ]);
      setItems(data.items);
      if (faqData.faq) setFaq(faqData.faq);
      setMemory(mem);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load, cycleId]);

  const approvedCount = items.reduce(
    (n, i) => n + i.communications.filter((c) => c.status === "approved" && c.comm_type === "letter").length,
    0,
  );

  async function batchGen(tone: "formal" | "informal") {
    setBusy(true);
    setSuccess("");
    try {
      const r = await generateLettersBatch(tone);
      setSuccess(`Создано писем: ${r.generated}. Раскройте компанию и нажмите «Утвердить».`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onApprove(commId: number) {
    setBusy(true);
    try {
      await approveCommunication(commId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onCompletePhase() {
    setBusy(true);
    try {
      await completeCommsPhase();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGuard>
      <CuratorGuard>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar className="md:sticky md:top-0 md:h-screen" />
        <main className="flex-1 p-6 md:p-10">
          <CycleBanner />
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <Link href="/dashboard" className="flex items-center gap-2 text-sm text-muted hover:text-accent">
              <ArrowLeft className="h-4 w-4" />
              К дашборду
            </Link>
            <h1 className="text-2xl font-bold">Фаза 3 — Коммуникации</h1>
          </div>

          <p className="mb-4 text-sm text-muted">
            Утверждено писем: <strong className="text-text">{approvedCount}</strong> / {items.length}
            {memory && (
              <>
                {" "}
                · Паттернов памяти: <strong>{memory.patterns_success}</strong> / {memory.outcomes_total}{" "}
                исходов
              </>
            )}
          </p>

          {canEdit && memory && (
            <section className="mb-6 flex flex-wrap gap-2 rounded-xl border border-border bg-surface-2 p-4 text-sm">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const r = await syncStrategyMemory();
                    setSuccess(`Память: обновлено ${r.patterns_upserted} паттернов.`);
                    setMemory(await fetchMemoryStats());
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Ошибка");
                  } finally {
                    setBusy(false);
                  }
                }}
                className="rounded-lg border border-border px-3 py-1.5 hover:bg-surface"
              >
                Синхр. память
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const r = await exportQloraDataset();
                    setSuccess(`QLoRA датасет: ${r.records} записей → ${r.path}`);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Ошибка экспорта");
                  } finally {
                    setBusy(false);
                  }
                }}
                className="rounded-lg border border-border px-3 py-1.5 hover:bg-surface"
              >
                Экспорт QLoRA
              </button>
            </section>
          )}

          {canEdit && (
            <section className="mb-6 flex flex-wrap gap-2 rounded-2xl border border-border bg-surface-2 p-4">
              <button
                type="button"
                disabled={busy}
                onClick={() => batchGen("formal")}
                className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {busy ? <Loader2 className="inline h-4 w-4 animate-spin" /> : null} Письма (формальные)
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => batchGen("informal")}
                className="rounded-xl border border-border px-4 py-2 text-sm hover:bg-surface"
              >
                Письма (неформальные)
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const f = await generateFaq();
                    setFaq(f);
                    setSuccess("FAQ создан.");
                    setError("");
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Ошибка");
                  } finally {
                    setBusy(false);
                  }
                }}
                className="rounded-xl border border-border px-4 py-2 text-sm"
              >
                Сгенерировать FAQ
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const blob = await downloadPresentationPdf();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "procompetencies_presentation.pdf";
                    a.click();
                    URL.revokeObjectURL(url);
                    setSuccess("PDF презентация скачана.");
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Ошибка PDF");
                  } finally {
                    setBusy(false);
                  }
                }}
                className="rounded-xl border border-border px-4 py-2 text-sm"
              >
                PDF презентация
              </button>
              {approvedCount > 0 && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={onCompletePhase}
                  className="rounded-xl border border-emerald-500/50 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-400"
                >
                  Завершить фазу 3
                </button>
              )}
            </section>
          )}

          {faq && (
            <section className="mb-8 rounded-2xl border border-border bg-surface-2 p-5">
              <h2 className="mb-2 font-semibold">FAQ для партнёров</h2>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-muted">{faq.body}</pre>
            </section>
          )}

          {success && (
            <p className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
              {success}
            </p>
          )}

          {items.length === 0 && !loading && (
            <p className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
              Список пуст. Вернитесь в «Компании»: Top-3 в шорт-лист → Утвердить шорт-лист.
            </p>
          )}

          {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
          {loading && <p className="text-muted">Загрузка…</p>}

          <div className="space-y-4">
            {items.map((item) => {
              const letter = item.communications.find((c) => c.comm_type === "letter");
              const isOpen = expanded === item.company.id;
              return (
                <article key={item.company.id} className="rounded-2xl border border-border bg-surface-2 p-4">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between text-left"
                    onClick={async () => {
                      const next = isOpen ? null : item.company.id;
                      setExpanded(next);
                      const letter = item.communications.find((c) => c.comm_type === "letter");
                      if (next && letter && !versions[letter.id]) {
                        try {
                          const v = await fetchCommunicationVersions(letter.id);
                          setVersions((prev) => ({ ...prev, [letter.id]: v.versions }));
                        } catch {
                          /* ignore */
                        }
                      }
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <Mail className="h-5 w-5 text-accent" />
                      <span className="font-semibold">{item.company.name}</span>
                    </div>
                    <span
                      className={clsx(
                        "rounded px-2 py-0.5 text-xs",
                        letter?.status === "approved"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : letter
                            ? "bg-amber-500/20 text-amber-400"
                            : "bg-surface text-muted",
                      )}
                    >
                      {letter?.status === "approved" ? "утверждено" : letter ? "черновик" : "нет письма"}
                    </span>
                  </button>

                  {isOpen && (
                    <div className="mt-4 space-y-4 border-t border-border pt-4">
                      {!letter && canEdit && (
                        <div className="flex gap-2">
                          <button
                            type="button"
                            disabled={busy}
                            onClick={async () => {
                              setBusy(true);
                              try {
                                await generateLetter(item.company.id, "formal");
                                await load();
                              } finally {
                                setBusy(false);
                              }
                            }}
                            className="text-sm text-accent hover:underline"
                          >
                            Сгенерировать письмо
                          </button>
                        </div>
                      )}
                      {letter && (
                        <>
                          <div>
                            <label className="text-xs text-muted">Тема</label>
                            <p className="font-medium">{letter.subject}</p>
                          </div>
                          {letter.value_proposition && (
                            <div className="rounded-lg bg-surface p-3 text-sm text-muted">
                              <strong className="text-text">Value proposition</strong>
                              <pre className="mt-1 whitespace-pre-wrap">{letter.value_proposition}</pre>
                            </div>
                          )}
                          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-surface p-3 text-sm">
                            {letter.body}
                          </pre>
                          {canEdit && letter.status !== "approved" && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => onApprove(letter.id)}
                              className="flex items-center gap-1 rounded-lg bg-emerald-500/20 px-3 py-1.5 text-sm text-emerald-400"
                            >
                              <Send className="h-4 w-4" /> Утвердить письмо
                            </button>
                          )}
                          {versions[letter.id]?.length ? (
                            <div>
                              <h3 className="mb-2 text-sm font-medium">История версий</h3>
                              <ul className="max-h-40 space-y-2 overflow-auto text-xs text-muted">
                                {versions[letter.id].map((v) => (
                                  <li key={v.id} className="rounded border border-border p-2">
                                    v{v.version} · {v.edited_by || "—"} ·{" "}
                                    {v.created_at ? new Date(v.created_at).toLocaleString() : ""}
                                    {v.subject && <div className="mt-1 text-text">{v.subject}</div>}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </>
                      )}
                      {item.touch_plan.length > 0 && (
                        <div>
                          <h3 className="mb-2 text-sm font-medium">План касаний</h3>
                          <ul className="space-y-1 text-xs text-muted">
                            {item.touch_plan.map((t) => (
                              <li key={t.id}>
                                День {t.days_after_start}: {t.title} ({t.channel}) — {t.status}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </main>
      </div>
    </CuratorGuard>
    </AuthGuard>
  );
}
