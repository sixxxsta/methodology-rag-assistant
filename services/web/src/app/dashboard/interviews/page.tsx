"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { AppShell } from "@/components/app-shell";
import { CuratorGuard } from "@/components/curator-guard";
import { Sidebar } from "@/components/sidebar";
import {
  approveProjectInterview,
  fetchPendingInterviews,
  rejectProjectInterview,
  type PendingInterview,
} from "@/lib/api";
import { canUseEdAgent, getUser } from "@/lib/auth";
import { ArrowLeft, ClipboardList, ExternalLink, Loader2 } from "lucide-react";

function formatWhen(iso?: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16).replace("T", " ");
  }
}

export default function InterviewsPage() {
  const [items, setItems] = useState<PendingInterview[]>([]);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [rejectInterviewId, setRejectInterviewId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const canEdit = canUseEdAgent(getUser());

  const busy = (key: string) => busyKey === key;

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await fetchPendingInterviews();
      setItems(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  return (
    <AuthGuard>
      <CuratorGuard>
        <AppShell sidebar={<Sidebar className="hidden md:flex" />}>
          <div className="p-6 md:p-10">

            <div className="mb-6 flex flex-wrap items-center gap-3">
              <Link
                href="/dashboard"
                className="flex items-center gap-2 text-sm text-muted hover:text-accent"
              >
                <ArrowLeft className="h-4 w-4" />
                К дашборду
              </Link>
              <h1 className="flex items-center gap-2 text-2xl font-bold">
                <ClipboardList className="h-7 w-7 text-amber-400" />
                Собеседования команд
              </h1>
            </div>

            <p className="mb-6 max-w-2xl text-sm text-muted">
              Здесь отображаются ответы команд по всем вашим проектам в каталоге (включая
              архивные циклы). Примите или отклоните заявку — после одобрения лидер сможет
              выбрать проект для команды.
            </p>

            {loading && <p className="text-muted">Загрузка…</p>}
            {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
            {info && (
              <p className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
                {info}
              </p>
            )}

            {!loading && items.length === 0 && (
              <div className="rounded-xl border border-border bg-surface-2 px-6 py-10 text-center">
                <ClipboardList className="mx-auto mb-3 h-10 w-10 text-muted" />
                <p className="font-medium text-text">Нет заявок на проверке</p>
                <p className="mt-2 text-sm text-muted">
                  Когда команда отправит ответы на собеседование, они появятся здесь.
                </p>
                <Link
                  href="/catalog"
                  className="mt-4 inline-flex items-center gap-1 text-sm text-accent hover:underline"
                >
                  Открыть каталог
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              </div>
            )}

            {!loading && items.length > 0 && (
              <ul className="space-y-5">
                {items.map((iv) => (
                  <li
                    key={iv.id}
                    className="rounded-2xl border border-amber-500/25 bg-surface-2 p-5 shadow-sm"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-lg font-semibold text-text">{iv.team_name}</p>
                        <p className="mt-1 text-sm text-muted">
                          Проект:{" "}
                          <Link
                            href={`/catalog/${iv.project_id}`}
                            className="text-accent hover:underline"
                          >
                            {iv.project_title}
                          </Link>
                        </p>
                        <p className="mt-1 text-xs text-muted">
                          Лидер: {iv.leader_fio || iv.leader_email}
                          {iv.cycle_name && (
                            <span className="ml-2">· цикл: {iv.cycle_name}</span>
                          )}
                          {iv.submitted_at && (
                            <span className="ml-2">· отправлено {formatWhen(iv.submitted_at)}</span>
                          )}
                        </p>
                      </div>
                      <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-200">
                        На проверке
                      </span>
                    </div>

                    <div className="mt-4 space-y-3">
                      {iv.questions.map((q, i) => (
                        <div
                          key={i}
                          className="rounded-xl border border-border/60 bg-surface px-4 py-3"
                        >
                          <p className="text-xs font-medium text-muted">
                            {i + 1}. {q}
                          </p>
                          <p className="mt-2 text-sm leading-relaxed text-text whitespace-pre-wrap">
                            {iv.answers[i]?.trim() || "—"}
                          </p>
                        </div>
                      ))}
                    </div>

                    {canEdit && (
                      <div className="mt-4 flex flex-wrap gap-2 border-t border-border/60 pt-4">
                        <button
                          type="button"
                          disabled={!!busyKey}
                          onClick={async () => {
                            setBusyKey(`approve:${iv.id}`);
                            setInfo("");
                            try {
                              const res = await approveProjectInterview(iv.id);
                              if (res.team_claimed) {
                                setInfo(
                                  `Команда «${iv.team_name}» одобрена и зачислена на проект «${iv.project_title}»`,
                                );
                              } else if (res.claim_note) {
                                setInfo(
                                  `Собеседование одобрено, но зачислить команду не удалось: ${res.claim_note}`,
                                );
                              } else {
                                setInfo(`Команда «${iv.team_name}» одобрена`);
                              }
                              await load();
                            } catch (e) {
                              setError(e instanceof Error ? e.message : "Ошибка");
                            } finally {
                              setBusyKey(null);
                            }
                          }}
                          className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
                        >
                          {busy(`approve:${iv.id}`) && (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          )}
                          Принять команду
                        </button>
                        <button
                          type="button"
                          disabled={!!busyKey}
                          onClick={() => {
                            setRejectReason("");
                            setRejectInterviewId(iv.id);
                          }}
                          className="rounded-xl border border-red-500/40 px-4 py-2 text-sm text-red-400 disabled:opacity-50"
                        >
                          Отклонить
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {rejectInterviewId != null && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
                role="dialog"
                aria-modal="true"
              >
                <div className="w-full max-w-md rounded-2xl border border-border bg-surface-2 p-6 shadow-xl">
                  <h2 className="text-lg font-semibold text-text">Отклонить собеседование</h2>
                  <p className="mt-2 text-sm text-muted">
                    Комментарий для команды (обязательно):
                  </p>
                  <textarea
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    rows={4}
                    className="mt-3 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm"
                    autoFocus
                  />
                  <div className="mt-6 flex flex-wrap justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setRejectInterviewId(null)}
                      className="rounded-xl border border-border px-4 py-2 text-sm"
                    >
                      Нет
                    </button>
                    <button
                      type="button"
                      disabled={!rejectReason.trim() || busy(`reject:${rejectInterviewId}`)}
                      onClick={async () => {
                        const id = rejectInterviewId;
                        setBusyKey(`reject:${id}`);
                        setInfo("");
                        try {
                          await rejectProjectInterview(id, rejectReason.trim());
                          setRejectInterviewId(null);
                          setInfo("Собеседование отклонено, команда получит комментарий");
                          await load();
                        } catch (e) {
                          setError(e instanceof Error ? e.message : "Ошибка");
                        } finally {
                          setBusyKey(null);
                        }
                      }}
                      className="rounded-xl bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
                    >
                      Да, отклонить
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </AppShell>
      </CuratorGuard>
    </AuthGuard>
  );
}
