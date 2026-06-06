"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { AppShell } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { CycleBanner } from "@/components/cycle-banner";
import { CuratorGuard } from "@/components/curator-guard";
import { Sidebar } from "@/components/sidebar";
import {
  approveProject,
  completeProjectsPhase,
  createStandaloneProject,
  deleteProject,
  extendCatalogProject,
  fetchProjectsDashboard,
  generateProjectTz,
  publishProject,
  syncProjectRoles,
  updateProject,
} from "@/lib/api";
import { canUseEdAgent, getUser } from "@/lib/auth";
import { useActiveCycleId } from "@/lib/use-cycle";
import clsx from "clsx";
import { ArrowLeft, BookOpen, FileText, Loader2 } from "lucide-react";

type Dash = Awaited<ReturnType<typeof fetchProjectsDashboard>>;

export default function ProjectsPage() {
  const [data, setData] = useState<Dash | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [editSpec, setEditSpec] = useState("");
  const [editTeamSize, setEditTeamSize] = useState(4);
  const [editMaxTeams, setEditMaxTeams] = useState(3);
  const [editInterviewRequired, setEditInterviewRequired] = useState(false);
  const [standaloneTitle, setStandaloneTitle] = useState("");
  const [standaloneSpec, setStandaloneSpec] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const canEdit = canUseEdAgent(getUser());
  const cycleId = useActiveCycleId();

  const busy = (key: string) => busyKey === key;

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
    setLoading(true);
    load();
  }, [load, cycleId]);

  async function onGenerate(companyId: number, agreementId: number) {
    const key = `generate:${agreementId}`;
    setBusyKey(key);
    try {
      const p = await generateProjectTz(companyId, agreementId);
      setExpanded(p.id as number);
      setEditSpec((p.spec_markdown as string) || "");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка генерации");
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <AuthGuard>
      <CuratorGuard>
      <AppShell sidebar={<Sidebar className="hidden md:flex" />}>
        <div className="p-6 md:p-10">
          <CycleBanner />
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
            {(data?.pending_interviews?.length ?? 0) > 0 && (
              <Link
                href="/dashboard/interviews"
                className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-200 hover:border-amber-500/50"
              >
                Собеседования: {data!.pending_interviews!.length}
              </Link>
            )}
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

              {canEdit && (
                <section className="mb-8 rounded-xl border border-border bg-surface-2 p-4">
                  <h2 className="mb-2 font-semibold">Свой проект без партнёра</h2>
                  <p className="mb-3 text-xs text-muted">
                    Создайте проект сразу в каталог, без прохождения всех пяти фаз EdAgent.
                  </p>
                  <div className="space-y-3">
                    <input
                      type="text"
                      value={standaloneTitle}
                      onChange={(e) => setStandaloneTitle(e.target.value)}
                      placeholder="Название проекта"
                      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                    />
                    <textarea
                      value={standaloneSpec}
                      onChange={(e) => setStandaloneSpec(e.target.value)}
                      rows={6}
                      placeholder="Краткое ТЗ (необязательно)"
                      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm leading-relaxed"
                    />
                    <button
                      type="button"
                      disabled={!standaloneTitle.trim() || busy("standalone")}
                      onClick={async () => {
                        setBusyKey("standalone");
                        setError("");
                        try {
                          const p = await createStandaloneProject({
                            title: standaloneTitle.trim(),
                            spec_markdown: standaloneSpec.trim() || undefined,
                            team_size: editTeamSize,
                            max_teams: editMaxTeams,
                          });
                          setStandaloneTitle("");
                          setStandaloneSpec("");
                          setExpanded(p.id);
                          setEditSpec((p.spec_markdown as string) || "");
                          await load();
                        } catch (e) {
                          setError(e instanceof Error ? e.message : "Ошибка");
                        } finally {
                          setBusyKey(null);
                        }
                      }}
                      className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
                    >
                      {busy("standalone") ? "Создание…" : "Создать проект"}
                    </button>
                  </div>
                </section>
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
                          disabled={busy(`generate:${p.agreement_id}`)}
                          onClick={() => onGenerate(p.company_id, p.agreement_id)}
                          className="mt-3 flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-xs text-white disabled:opacity-50"
                        >
                          {busy(`generate:${p.agreement_id}`) ? (
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
                              {proj.approved_by_fio && ` · куратор: ${proj.approved_by_fio}`}
                            </p>
                            {(proj.team_size || proj.max_teams || proj.duration_weeks) && (
                              <p className="mt-1 text-xs text-muted">
                                В команде: до {Math.min(proj.team_size ?? 5, 5)} чел. · слотов
                                команд: {proj.max_teams ?? 3} · срок: {proj.duration_weeks ?? "—"}{" "}
                                нед.
                                {proj.interview_required && " · собеседование обязательно"}
                              </p>
                            )}
                            {(proj.claimed_teams?.length ?? 0) > 0 && (
                              <p className="mt-2 text-xs text-muted">
                                Выбрали:{" "}
                                {proj.claimed_teams!
                                  .map((t) => `${t.team_name} (${t.leader_fio || t.leader_email})`)
                                  .join(", ")}
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
                                setEditInterviewRequired(proj.interview_required ?? false);
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
                                <label className="flex items-center gap-2 text-xs text-muted">
                                  <input
                                    type="checkbox"
                                    checked={editInterviewRequired}
                                    onChange={(e) => setEditInterviewRequired(e.target.checked)}
                                    className="rounded border-border"
                                  />
                                  Только после собеседования
                                </label>
                              </div>
                            )}
                            <textarea
                              value={editSpec}
                              onChange={(e) => setEditSpec(e.target.value)}
                              rows={12}
                              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm leading-relaxed"
                              readOnly={!canEdit}
                            />
                            {canEdit && (
                              <div className="flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  disabled={busy(`save:${proj.id}`)}
                                  onClick={async () => {
                                    setBusyKey(`save:${proj.id}`);
                                    try {
                                      await updateProject(proj.id, {
                                        spec_markdown: editSpec,
                                        team_size: editTeamSize,
                                        max_teams: editMaxTeams,
                                        interview_required: editInterviewRequired,
                                      });
                                      await load();
                                    } finally {
                                      setBusyKey(null);
                                    }
                                  }}
                                  className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-50"
                                >
                                  Сохранить ТЗ и параметры команд
                                </button>
                                <button
                                  type="button"
                                  disabled={busy(`roles:${proj.id}`)}
                                  onClick={async () => {
                                    setBusyKey(`roles:${proj.id}`);
                                    try {
                                      await syncProjectRoles(proj.id);
                                      await load();
                                    } catch (e) {
                                      setError(e instanceof Error ? e.message : "Ошибка");
                                    } finally {
                                      setBusyKey(null);
                                    }
                                  }}
                                  className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-50"
                                >
                                  Обновить роли из ТЗ
                                </button>
                                {proj.status === "draft" && (
                                  <button
                                    type="button"
                                    disabled={busy(`approve:${proj.id}`)}
                                    onClick={async () => {
                                      setBusyKey(`approve:${proj.id}`);
                                      try {
                                        await approveProject(proj.id);
                                        await load();
                                      } finally {
                                        setBusyKey(null);
                                      }
                                    }}
                                    className="rounded-lg bg-accent px-3 py-1.5 text-xs text-white disabled:opacity-50"
                                  >
                                    Утвердить ТЗ
                                  </button>
                                )}
                                {proj.status === "approved" && !proj.catalog_visible && (
                                  <button
                                    type="button"
                                    disabled={
                                      busy(`publish:${proj.id}`) || proj.publish_ready === false
                                    }
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
                                      setBusyKey(`publish:${proj.id}`);
                                      try {
                                        await publishProject(proj.id, opts);
                                        await load();
                                      } finally {
                                        setBusyKey(null);
                                      }
                                    }}
                                    className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs text-white disabled:opacity-50"
                                  >
                                    В каталог
                                  </button>
                                )}
                                {canEdit &&
                                  proj.can_extend_catalog &&
                                  (proj.catalog_visible ||
                                    proj.catalog_mode === "temporary") && (
                                    <button
                                      type="button"
                                      disabled={busy(`extend:${proj.id}`)}
                                      onClick={async () => {
                                        const months = window.prompt(
                                          "Продлить показ в каталоге на сколько месяцев?",
                                          "5",
                                        );
                                        if (!months) return;
                                        const n = Number(months);
                                        if (!Number.isFinite(n) || n < 1 || n > 60) {
                                          setError("Укажите число месяцев от 1 до 60");
                                          return;
                                        }
                                        setBusyKey(`extend:${proj.id}`);
                                        setError("");
                                        try {
                                          await extendCatalogProject(proj.id, n);
                                          await load();
                                        } catch (e) {
                                          setError(
                                            e instanceof Error ? e.message : "Ошибка",
                                          );
                                        } finally {
                                          setBusyKey(null);
                                        }
                                      }}
                                      className="rounded-lg border border-amber-500/50 px-3 py-1.5 text-xs text-amber-300 hover:bg-amber-500/10 disabled:opacity-50"
                                    >
                                      Продлить в каталоге
                                    </button>
                                  )}
                                {canEdit && proj.can_delete && (
                                  <button
                                    type="button"
                                    disabled={busy(`delete:${proj.id}`)}
                                    onClick={() => setConfirmDeleteId(proj.id)}
                                    className="rounded-lg border border-red-500/50 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                                  >
                                    Удалить проект
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
                  disabled={busy("complete-phase")}
                  onClick={async () => {
                    setBusyKey("complete-phase");
                    try {
                      await completeProjectsPhase();
                      await load();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Ошибка");
                    } finally {
                      setBusyKey(null);
                    }
                  }}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
                >
                  Завершить фазу 5
                </button>
              )}
            </>
          )}

          <ConfirmDialog
            open={confirmDeleteId != null}
            title="Удаление проекта"
            message="Вы действительно хотите удалить этот проект? Это действие нельзя отменить."
            confirmLabel="Да"
            cancelLabel="Нет"
            danger
            onCancel={() => setConfirmDeleteId(null)}
            onConfirm={async () => {
              if (confirmDeleteId == null) return;
              const id = confirmDeleteId;
              setConfirmDeleteId(null);
              setBusyKey(`delete:${id}`);
              setError("");
              try {
                await deleteProject(id);
                setExpanded(null);
                await load();
              } catch (e) {
                setError(e instanceof Error ? e.message : "Ошибка");
              } finally {
                setBusyKey(null);
              }
            }}
          />
        </div>
      </AppShell>
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
