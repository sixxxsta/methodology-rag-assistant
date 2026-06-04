"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { CuratorGuard } from "@/components/curator-guard";
import { Sidebar } from "@/components/sidebar";
import { approveIndustry, fetchDashboard, resolveEscalation } from "@/lib/api";
import { canUseEdAgent, getUser } from "@/lib/auth";
import type { DashboardData } from "@/lib/types";
import clsx from "clsx";
import {
  AlertCircle,
  ArrowLeft,
  BarChart3,
  Building2,
  CheckCircle2,
  Mail,
  Send,
  FolderKanban,
  Lock,
  PlayCircle,
} from "lucide-react";

const STATUS_LABEL: Record<string, string> = {
  locked: "Ожидает",
  active: "В работе",
  completed: "Завершена",
  blocked: "Заблокирована",
};

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle2 className="h-5 w-5 text-emerald-400" />;
  if (status === "active") return <PlayCircle className="h-5 w-5 text-accent" />;
  if (status === "blocked") return <AlertCircle className="h-5 w-5 text-amber-400" />;
  return <Lock className="h-5 w-5 text-muted" />;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [industry, setIndustry] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const d = await fetchDashboard();
      setData(d);
      setIndustry((prev) => prev || d.workspace.industry || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onApproveIndustry() {
    if (!industry.trim()) return;
    setBusy(true);
    try {
      const d = await approveIndustry(industry.trim());
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onResolve(id: number) {
    setBusy(true);
    try {
      await resolveEscalation(id);
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
          <div className="mb-8 flex flex-wrap items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-2 text-sm text-muted hover:text-accent"
            >
              <ArrowLeft className="h-4 w-4" />
              К чату
            </Link>
            <h1 className="text-2xl font-bold">EdAgent — цикл партнёрства</h1>
          </div>

          {loading && <p className="text-muted">Загрузка…</p>}
          {error && (
            <p className="mb-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-400">{error}</p>
          )}

          {data && (
            <>
              {data.workspace.phases.find((p) => p.key === "industry_analysis")?.status ===
                "active" && (
                <Link
                  href="/dashboard/competencies"
                  className="mb-6 flex items-center gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-4 transition hover:bg-accent/15"
                >
                  <BarChart3 className="h-6 w-6 text-accent" />
                  <div>
                    <p className="font-semibold">Анализ компетенций</p>
                    <p className="text-sm text-muted">
                      Сбор вакансий HH.ru и матрица соответствия программе
                    </p>
                  </div>
                </Link>
              )}

              {data.workspace.phases.find((p) => p.key === "projects")?.status ===
                "active" && (
                <Link
                  href="/dashboard/projects"
                  className="mb-6 flex items-center gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-4 transition hover:bg-accent/15"
                >
                  <FolderKanban className="h-6 w-6 text-accent" />
                  <div>
                    <p className="font-semibold">Проекты и ТЗ</p>
                    <p className="text-sm text-muted">
                      Генерация ТЗ, утверждение, каталог для студентов
                    </p>
                  </div>
                </Link>
              )}

              {data.workspace.phases.find((p) => p.key === "outreach")?.status ===
                "active" && (
                <Link
                  href="/dashboard/outreach"
                  className="mb-6 flex items-center gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-4 transition hover:bg-accent/15"
                >
                  <Send className="h-6 w-6 text-accent" />
                  <div>
                    <p className="font-semibold">Outreach и квалификация</p>
                    <p className="text-sm text-muted">Отправка, ответы, follow-up, соглашения</p>
                  </div>
                </Link>
              )}

              {data.workspace.phases.find((p) => p.key === "communication")?.status ===
                "active" && (
                <Link
                  href="/dashboard/communications"
                  className="mb-6 flex items-center gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-4 transition hover:bg-accent/15"
                >
                  <Mail className="h-6 w-6 text-accent" />
                  <div>
                    <p className="font-semibold">Коммуникации с партнёрами</p>
                    <p className="text-sm text-muted">Письма, FAQ, план касаний, утверждение</p>
                  </div>
                </Link>
              )}

              {data.workspace.phases.find((p) => p.key === "company_scoring")?.status ===
                "active" && (
                <Link
                  href="/dashboard/companies"
                  className="mb-6 flex items-center gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-4 transition hover:bg-accent/15"
                >
                  <Building2 className="h-6 w-6 text-accent" />
                  <div>
                    <p className="font-semibold">Поиск и скоринг компаний</p>
                    <p className="text-sm text-muted">HH.ru, Top-10/100, верификация шорт-листа</p>
                  </div>
                </Link>
              )}

              <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                {data.workspace.phases.map((phase) => (
                  <div
                    key={phase.key}
                    className={clsx(
                      "rounded-2xl border p-4 transition",
                      phase.status === "active"
                        ? "border-accent/50 bg-accent/5"
                        : "border-border bg-surface-2",
                    )}
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-medium text-muted">Фаза {phase.order}</span>
                      {statusIcon(phase.status)}
                    </div>
                    <h2 className="font-semibold leading-tight">{phase.title}</h2>
                    <p className="mt-1 text-xs text-muted line-clamp-2">{phase.description}</p>
                    <div className="mt-3 flex items-center justify-between text-xs">
                      <span className="text-muted">{STATUS_LABEL[phase.status] ?? phase.status}</span>
                      <span className="font-medium">{phase.progress_pct}%</span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border">
                      <div
                        className="h-full rounded-full bg-accent transition-all"
                        style={{ width: `${phase.progress_pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {data.escalations.filter((e) => e.status === "open").length > 0 && (
                <section className="mb-8 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-6">
                  <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
                    <AlertCircle className="h-5 w-5 text-amber-400" />
                    Эскалации ({data.workspace.open_escalations})
                  </h2>
                  <ul className="space-y-4">
                    {data.escalations
                      .filter((e) => e.status === "open")
                      .map((esc) => (
                        <li
                          key={esc.id}
                          className="rounded-xl border border-border bg-surface-2 p-4"
                        >
                          <p className="font-medium">{esc.title}</p>
                          <p className="mt-1 text-sm text-muted">{esc.description}</p>
                          {esc.level === 1 && canUseEdAgent(getUser()) && (
                            <div className="mt-4 flex flex-wrap gap-2">
                              <input
                                type="text"
                                value={industry}
                                onChange={(e) => setIndustry(e.target.value)}
                                placeholder="Отрасль, напр. IT / FinTech"
                                className="min-w-[200px] flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                              />
                              <button
                                type="button"
                                disabled={busy || !industry.trim()}
                                onClick={onApproveIndustry}
                                className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                              >
                                Утвердить отрасль
                              </button>
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => onResolve(esc.id)}
                                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-surface"
                              >
                                Закрыть
                              </button>
                            </div>
                          )}
                          {esc.level !== 1 && canUseEdAgent(getUser()) && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => onResolve(esc.id)}
                              className="mt-3 rounded-lg border border-border px-4 py-2 text-sm hover:bg-surface"
                            >
                              Закрыть
                            </button>
                          )}
                        </li>
                      ))}
                  </ul>
                </section>
              )}

              <section className="rounded-2xl border border-border bg-surface-2 p-6">
                <h2 className="mb-4 text-lg font-semibold">Журнал действий</h2>
                {data.recent_audit.length === 0 ? (
                  <p className="text-sm text-muted">Пока пусто</p>
                ) : (
                  <ul className="space-y-2 text-sm">
                    {data.recent_audit.map((a) => (
                      <li
                        key={a.id}
                        className="flex flex-wrap gap-x-3 gap-y-1 border-b border-border/50 py-2 last:border-0"
                      >
                        <span className="text-muted">
                          {new Date(a.created_at).toLocaleString("ru-RU")}
                        </span>
                        <span className="text-accent">{a.action}</span>
                        <span>{a.actor_email}</span>
                        {a.details && <span className="text-muted">{a.details}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </main>
      </div>
    </CuratorGuard>
    </AuthGuard>
  );
}
