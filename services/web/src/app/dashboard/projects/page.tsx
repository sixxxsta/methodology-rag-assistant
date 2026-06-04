"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { CuratorGuard } from "@/components/curator-guard";
import { Sidebar } from "@/components/sidebar";
import {
  approveProject,
  completeProjectsPhase,
  fetchProjectsDashboard,
  generateProjectTz,
  publishProject,
  syncProjectRoles,
  updateProject,
} from "@/lib/api";
import { canUseEdAgent, getUser } from "@/lib/auth";
import clsx from "clsx";
import { ArrowLeft, BookOpen, FileText, Loader2 } from "lucide-react";

type Dash = Awaited<ReturnType<typeof fetchProjectsDashboard>>;

export default function ProjectsPage() {
  const [data, setData] = useState<Dash | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [editSpec, setEditSpec] = useState("");
  const [editTeamSize, setEditTeamSize] = useState(4);
  const [editMaxTeams, setEditMaxTeams] = useState(3);
  const canEdit = canUseEdAgent(getUser());

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await fetchProjectsDashboard());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onGenerate(companyId: number, agreementId: number) {
    setBusy(true);
    try {
      const p = await generateProjectTz(companyId, agreementId);
      setExpanded(p.id as number);
      setEditSpec((p.spec_markdown as string) || "");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка генерации");
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
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard"
              className="flex items-center gap-2 text-sm text-muted hover:text-accent"
            >
              <ArrowLeft className="h-4 w-4" />
              К дашборду
            </Link>
            <h1 className="text-2xl font-bold">Фаза 5 — Проекты и ТЗ</h1>
            <Link
              href="/catalog"
              className="ml-auto flex items-center gap-2 text-sm text-accent hover:underline"
            >
              <BookOpen className="h-4 w-4" />
              Каталог для студентов
            </Link>
          </div>

          {loading && <p className="text-muted">Загрузка…</p>}
          {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

          {data && (
            <>
              <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
                <Stat label="Партнёров" value={data.partners_count} />
                <Stat label="Проектов" value={data.projects_total} />
                <Stat label="В каталоге" value={data.catalog_published} />
                <Stat label="Прогресс фазы" value={data.phase_progress} suffix="%" />
              </div>

              {data.pending.length === 0 && (
                <p className="mb-6 rounded-lg border border-border bg-surface-2 px-4 py-3 text-sm text-muted">
                  Нет соглашений с партнёрами. Зафиксируйте соглашение в фазе Outreach.
                </p>
              )}

              <section className="mb-8">
                <h2 className="mb-3 font-semibold">Партнёры — генерация ТЗ</h2>
                <ul className="space-y-3">
                  {data.pending.map((p) => (
                    <li
                      key={p.agreement_id}
                      className="rounded-xl border border-border bg-surface-2 p-4"
                    >
                      <p className="font-medium">{p.company_name}</p>
                      <p className="mt-1 text-xs text-muted line-clamp-2">
                        {p.agreement_summary}
                      </p>
                      <p className="mt-1 text-xs">
                        Статус:{" "}
                        <span className="text-accent">
                          {p.project_status || "нет ТЗ"}
                        </span>
                      </p>
                      {canEdit && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => onGenerate(p.company_id, p.agreement_id)}
                          className="mt-3 flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-xs text-white disabled:opacity-50"
                        >
                          {busy ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <FileText className="h-3 w-3" />
                          )}
                          Сгенерировать ТЗ (LLM)
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </section>

              <section className="mb-8">
                <h2 className="mb-3 font-semibold">Проекты</h2>
                {data.projects.length === 0 ? (
                  <p className="text-sm text-muted">Пока нет проектов.</p>
                ) : (
                  <ul className="space-y-4">
                    {data.projects.map((proj) => (
                      <li
                        key={proj.id}
                        className={clsx(
                          "rounded-xl border p-4",
                          proj.catalog_visible
                            ? "border-emerald-500/40 bg-emerald-500/5"
                            : "border-border bg-surface-2",
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="font-medium">{proj.title}</p>
                            <p className="text-xs text-muted">
                              {proj.company_name} · {proj.status}
                              {proj.catalog_visible && " · в каталоге"}
                            </p>
                            {(proj.team_size || proj.max_teams || proj.duration_weeks) && (
                              <p className="mt-1 text-xs text-muted">
                                В команде: до {Math.min(proj.team_size ?? 5, 5)} чел. · слотов
                                команд: {proj.max_teams ?? 3} · срок: {proj.duration_weeks ?? "—"}{" "}
                                нед.
                              </p>
                            )}
                            {proj.catalog_visible && proj.catalog_expiry_soon && (
                              <p className="mt-1 text-xs text-amber-400">
                                Каталог: снимется через {proj.catalog_expiry_soon.days_left} дн. (
                                {proj.catalog_expiry_soon.until.slice(0, 10)})
                              </p>
                            )}
                            {proj.status === "approved" &&
                              !proj.catalog_visible &&
                              proj.publish_ready === false &&
                              proj.publish_block_reason && (
                                <p className="mt-1 text-xs text-amber-400">
                                  {proj.publish_block_reason}
                                </p>
                              )}
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              const open = expanded === proj.id ? null : proj.id;
                              setExpanded(open);
                              if (open === proj.id) {
                                setEditSpec(proj.spec_markdown || "");
                                setEditTeamSize(Math.min(proj.team_size ?? 4, 5));
                                setEditMaxTeams(proj.max_teams ?? 3);
                              }
                            }}
                            className="text-xs text-accent hover:underline"
                          >
                            {expanded === proj.id ? "Свернуть" : "ТЗ"}
                          </button>
                        </div>

                        {expanded === proj.id && (
                          <div className="mt-4 space-y-3">
                            {canEdit && (
                              <div className="flex flex-wrap gap-4 rounded-lg border border-border/60 bg-surface p-3">
                                <label className="text-xs text-muted">
                                  Человек в команде (макс. 5)
                                  <input
                                    type="number"
                                    min={1}
                                    max={5}
                                    value={editTeamSize}
                                    onChange={(e) =>
                                      setEditTeamSize(
                                        Math.min(5, Math.max(1, Number(e.target.value) || 1)),
                                      )
                                    }
                                    className="mt-1 block w-20 rounded-lg border border-border bg-surface-2 px-2 py-1.5 text-sm text-text"
                                  />
                                </label>
                                <label className="text-xs text-muted">
                                  Сколько команд может взять проект
                                  <input
                                    type="number"
                                    min={1}
                                    max={50}
                                    value={editMaxTeams}
                                    onChange={(e) =>
                                      setEditMaxTeams(
                                        Math.min(50, Math.max(1, Number(e.target.value) || 1)),
                                      )
                                    }
                                    className="mt-1 block w-20 rounded-lg border border-border bg-surface-2 px-2 py-1.5 text-sm text-text"
                                  />
                                </label>
                              </div>
                            )}
                            <textarea
                              value={editSpec}
                              onChange={(e) => setEditSpec(e.target.value)}
                              rows={12}
                              className="w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-xs"
                              readOnly={!canEdit}
                            />
                            {canEdit && (
                              <div className="flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={async () => {
                                    setBusy(true);
                                    try {
                                      await updateProject(proj.id, {
                                        spec_markdown: editSpec,
                                        team_size: editTeamSize,
                                        max_teams: editMaxTeams,
                                      });
                                      await load();
                                    } finally {
                                      setBusy(false);
                                    }
                                  }}
                                  className="rounded-lg border border-border px-3 py-1.5 text-xs"
                                >
                                  Сохранить ТЗ и параметры команд
                                </button>
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={async () => {
                                    setBusy(true);
                                    try {
                                      await syncProjectRoles(proj.id);
                                      await load();
                                    } catch (e) {
                                      setError(e instanceof Error ? e.message : "Ошибка");
                                    } finally {
                                      setBusy(false);
                                    }
                                  }}
                                  className="rounded-lg border border-border px-3 py-1.5 text-xs"
                                >
                                  Обновить роли из ТЗ
                                </button>
                                {proj.status === "draft" && (
                                  <button
                                    type="button"
                                    disabled={busy}
                                    onClick={async () => {
                                      setBusy(true);
                                      try {
                                        await approveProject(proj.id);
                                        await load();
                                      } finally {
                                        setBusy(false);
                                      }
                                    }}
                                    className="rounded-lg bg-accent px-3 py-1.5 text-xs text-white"
                                  >
                                    Утвердить ТЗ
                                  </button>
                                )}
                                {proj.status === "approved" && !proj.catalog_visible && (
                                  <button
                                    type="button"
                                    disabled={busy || proj.publish_ready === false}
                                    title={
                                      proj.publish_block_reason ||
                                      "Сначала укажите размер команды и число слотов"
                                    }
                                    onClick={async () => {
                                      if (proj.publish_ready === false) {
                                        setError(
                                          proj.publish_block_reason ||
                                            "Заполните параметры команд в ТЗ",
                                        );
                                        return;
                                      }
                                      const permanent = window.confirm(
                                        "Как долго проект будет в каталоге для студентов?\n\nOK — постоянно (каждый семестр новые команды)\nОтмена — только текущий проход (~5 месяцев)",
                                      );
                                      const opts = permanent
                                        ? { catalog_mode: "permanent" as const }
                                        : { catalog_mode: "temporary" as const, catalog_months: 5 };
                                      setBusy(true);
                                      try {
                                        await publishProject(proj.id, opts);
                                        await load();
                                      } finally {
                                        setBusy(false);
                                      }
                                    }}
                                    className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs text-white disabled:opacity-50"
                                  >
                                    В каталог
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {canEdit && data.catalog_published >= 1 && data.phase_status === "active" && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await completeProjectsPhase();
                      await load();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Ошибка");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
                >
                  Завершить фазу 5
                </button>
              )}
            </>
          )}
        </main>
      </div>
    </CuratorGuard>
    </AuthGuard>
  );
}

function Stat({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value: number;
  suffix?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-2 px-4 py-3">
      <p className="text-muted">{label}</p>
      <p className="text-2xl font-bold">
        {value}
        {suffix}
      </p>
    </div>
  );
}
