"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { CycleBanner } from "@/components/cycle-banner";
import { CuratorGuard } from "@/components/curator-guard";
import { Sidebar } from "@/components/sidebar";
import {
  fetchOutreachDashboard,
  recordAgreement,
  recordInboundResponse,
  sendFollowup,
  sendOutreachLetter,
} from "@/lib/api";
import { canUseEdAgent, getUser } from "@/lib/auth";
import { useActiveCycleId } from "@/lib/use-cycle";
import clsx from "clsx";
import { AlertTriangle, ArrowLeft, Send } from "lucide-react";

type Dash = Awaited<ReturnType<typeof fetchOutreachDashboard>>;

export default function OutreachPage() {
  const [data, setData] = useState<Dash | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [inboundCompany, setInboundCompany] = useState<number | "">("");
  const [inboundText, setInboundText] = useState("");
  const [agreementSummary, setAgreementSummary] = useState("");
  const canEdit = canUseEdAgent(getUser());
  const cycleId = useActiveCycleId();

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await fetchOutreachDashboard());
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

  useEffect(() => {
    if (data?.companies?.length && inboundCompany === "") {
      const first = data.companies.find((c) => c.in_shortlist) ?? data.companies[0];
      setInboundCompany(first.id);
    }
  }, [data, inboundCompany]);

  async function onSend(commId: number, useSmtp: boolean) {
    setBusy(true);
    try {
      await sendOutreachLetter(commId, useSmtp);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка отправки");
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
            <h1 className="text-2xl font-bold">Фаза 4 — Outreach</h1>
          </div>

          {loading && <p className="text-muted">Загрузка…</p>}
          {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
          {info && (
            <p className="mb-4 rounded-lg border border-accent/30 bg-accent/10 px-4 py-2 text-sm text-accent">
              {info}
            </p>
          )}

          {data && (
            <>
              <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
                <Stat label="Утверждено" value={data.letters_approved} />
                <Stat label="Отправлено" value={data.letters_sent} />
                <Stat label="Доставлено" value={data.letters_delivered} />
                <Stat label="Открыто" value={data.letters_opened} />
                <Stat label="В очереди" value={data.letters_pending} />
                <Stat label="Ответов" value={data.inbound_count} />
              </div>

              {!data.smtp_enabled && canEdit && (
                <p className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-300">
                  SMTP не настроен — используйте «Отметить отправленным» (ручная отправка).
                </p>
              )}

              <section className="mb-8">
                <h2 className="mb-3 font-semibold">Очередь отправки</h2>
                {data.queue.length === 0 ? (
                  <p className="text-sm text-muted">Нет писем в очереди. Утвердите письма в фазе 3.</p>
                ) : (
                  <ul className="space-y-3">
                    {data.queue.map((q) => (
                      <li key={q.id} className="rounded-xl border border-border bg-surface-2 p-4">
                        <p className="font-medium">{q.company_name}</p>
                        <p className="text-xs text-muted">{q.subject}</p>
                        {q.contact_email && (
                          <p className="mt-1 text-xs text-accent">{q.contact_email}</p>
                        )}
                        {canEdit && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => onSend(q.id, false)}
                              className="rounded-lg bg-accent px-3 py-1.5 text-xs text-white"
                            >
                              Отметить отправленным
                            </button>
                            {data.smtp_enabled && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => onSend(q.id, true)}
                                className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs"
                              >
                                <Send className="h-3 w-3" /> SMTP
                              </button>
                            )}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {data.followups.length > 0 && (
                <section className="mb-8">
                  <h2 className="mb-3 font-semibold">Follow-up (просрочены)</h2>
                  <ul className="space-y-2">
                    {data.followups.map((f) => (
                      <li
                        key={f.touch_id}
                        className="flex items-center justify-between rounded-lg border border-border px-4 py-2 text-sm"
                      >
                        <span>
                          {f.company_name} — {f.title}
                        </span>
                        {canEdit && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={async () => {
                              setBusy(true);
                              try {
                                await sendFollowup(f.touch_id);
                                await load();
                              } finally {
                                setBusy(false);
                              }
                            }}
                            className="text-accent hover:underline"
                          >
                            Отправить
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section className="mb-8">
                <h2 className="mb-3 font-semibold">Зафиксировать ответ компании</h2>
                <div className="rounded-xl border border-border bg-surface-2 p-4 space-y-3">
                  {data.companies.length === 0 ? (
                    <p className="text-sm text-muted">
                      Сначала найдите компании (фаза 2) и добавьте в шорт-лист.
                    </p>
                  ) : (
                    <select
                      value={inboundCompany === "" ? "" : String(inboundCompany)}
                      onChange={(e) =>
                        setInboundCompany(e.target.value ? Number(e.target.value) : "")
                      }
                      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                    >
                      {data.companies.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} (id {c.id})
                          {c.in_shortlist ? " · shortlist" : ""}
                        </option>
                      ))}
                    </select>
                  )}
                  <textarea
                    value={inboundText}
                    onChange={(e) => setInboundText(e.target.value)}
                    placeholder="Текст ответа от компании"
                    rows={4}
                    className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                  />
                  <button
                    type="button"
                    disabled={busy || !inboundCompany || !inboundText.trim()}
                    onClick={async () => {
                      if (inboundCompany === "") return;
                      setBusy(true);
                      try {
                        const r = await recordInboundResponse(
                          inboundCompany,
                          inboundText,
                        );
                        if (r.needs_human) {
                          setError(
                            `Эскалация: «${r.classification}» (${Math.round((r.classification_confidence ?? 0) * 100)}%, ${r.classification_method ?? "—"}). Нужен личный контакт.`,
                          );
                        } else if (r.classification) {
                          setInfo(
                            `Классификация: ${r.classification} (${Math.round((r.classification_confidence ?? 0) * 100)}%, ${r.classification_method ?? "—"})`,
                          );
                        }
                        setInboundText("");
                        await load();
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Ошибка");
                      } finally {
                        setBusy(false);
                      }
                    }}
                    className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
                  >
                    Обработать ответ
                  </button>
                </div>
              </section>

              <section className="mb-8">
                <h2 className="mb-3 font-semibold">Входящие (последние)</h2>
                <ul className="space-y-2 text-sm">
                  {data.recent_responses.map((r) => (
                    <li
                      key={r.id}
                      className={clsx(
                        "rounded-lg border px-3 py-2",
                        r.classification === "meeting_request" || r.classification === "interest"
                          ? "border-amber-500/40 bg-amber-500/5"
                          : "border-border",
                      )}
                    >
                      <div className="flex items-center gap-2">
                        {(r.classification === "interest" ||
                          r.classification === "meeting_request") && (
                          <AlertTriangle className="h-4 w-4 text-amber-400" />
                        )}
                        <strong>{r.company_name}</strong>
                        <span className="text-xs text-muted">
                          {r.classification}
                          {r.classification_confidence != null &&
                            ` · ${Math.round(r.classification_confidence * 100)}%`}
                          {r.classification_method && ` (${r.classification_method})`}
                        </span>
                        {r.auto_handled && (
                          <span className="text-xs text-emerald-400">авто</span>
                        )}
                      </div>
                      <p className="mt-1 text-muted line-clamp-2">{r.body}</p>
                    </li>
                  ))}
                </ul>
              </section>

              {canEdit && (
                <section className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
                  <h2 className="mb-2 font-semibold">Соглашение с партнёром</h2>
                  <textarea
                    value={agreementSummary}
                    onChange={(e) => setAgreementSummary(e.target.value)}
                    placeholder="Договорённости, задачи, контакты…"
                    rows={3}
                    className="mb-2 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                  />
                  <div className="flex flex-wrap gap-2">
                    <select
                      value={inboundCompany === "" ? "" : String(inboundCompany)}
                      onChange={(e) =>
                        setInboundCompany(e.target.value ? Number(e.target.value) : "")
                      }
                      className="min-w-[200px] flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                    >
                      {data.companies.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      disabled={busy || !agreementSummary.trim() || inboundCompany === ""}
                      onClick={async () => {
                        if (inboundCompany === "") return;
                        setBusy(true);
                        try {
                          await recordAgreement(inboundCompany, agreementSummary);
                          setAgreementSummary("");
                          await load();
                        } finally {
                          setBusy(false);
                        }
                      }}
                      className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
                    >
                      Сохранить соглашение
                    </button>
                  </div>
                </section>
              )}
            </>
          )}
        </main>
      </div>
    </CuratorGuard>
    </AuthGuard>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2 px-4 py-3">
      <p className="text-muted">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}
