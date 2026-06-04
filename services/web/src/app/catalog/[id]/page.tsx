"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";
import {
  enrollInProject,
  fetchCatalogProject,
  withdrawFromProject,
  type CatalogProjectDetail,
} from "@/lib/api";
import { getUser, isStudent } from "@/lib/auth";
import { ArrowLeft, BookOpen, Loader2 } from "lucide-react";

type Props = { params: Promise<{ id: string }> };

export default function CatalogProjectPage({ params }: Props) {
  const [projectId, setProjectId] = useState<number | null>(null);
  const [project, setProject] = useState<CatalogProjectDetail | null>(null);
  const [selectedRole, setSelectedRole] = useState<number | "">("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const student = isStudent(getUser());

  useEffect(() => {
    params.then((p) => setProjectId(Number(p.id)));
  }, [params]);

  const load = useCallback(async () => {
    if (!projectId || Number.isNaN(projectId)) return;
    setError("");
    setLoading(true);
    try {
      setProject(await fetchCatalogProject(projectId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  async function onEnroll() {
    if (!projectId) return;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const roleId = selectedRole === "" ? undefined : Number(selectedRole);
      await enrollInProject(projectId, roleId);
      setInfo("Вы записаны на проект");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка записи");
    } finally {
      setBusy(false);
    }
  }

  async function onWithdraw() {
    if (!projectId) return;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      await withdrawFromProject(projectId);
      setInfo("Запись отменена");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  const canEnroll =
    student &&
    !project?.my_enrollment &&
    (project?.seats_left ?? 0) > 0;

  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar className="md:sticky md:top-0 md:h-screen" />
        <main className="flex-1 p-6 md:p-10">
          <Link
            href="/catalog"
            className="mb-6 inline-flex items-center gap-2 text-sm text-muted hover:text-accent"
          >
            <ArrowLeft className="h-4 w-4" />
            К каталогу
          </Link>

          {loading && <p className="text-muted">Загрузка…</p>}
          {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
          {info && (
            <p className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
              {info}
            </p>
          )}

          {project && (
            <article className="max-w-3xl">
              <h1 className="flex items-start gap-2 text-2xl font-bold leading-snug">
                <BookOpen className="mt-1 h-7 w-7 shrink-0 text-accent" />
                {project.title}
              </h1>
              {project.company_name && (
                <p className="mt-2 text-accent">{project.company_name}</p>
              )}
              <div className="mt-4 flex flex-wrap gap-4 text-sm text-muted">
                {project.team_size != null && <span>Команда: {project.team_size}</span>}
                {project.duration_weeks != null && (
                  <span>Срок: {project.duration_weeks} нед.</span>
                )}
                {project.competencies && (
                  <span>Компетенции: {project.competencies}</span>
                )}
                <span>
                  Мест: {project.enrollment_count ?? 0}/{project.team_size ?? "—"} ·
                  свободно {project.seats_left ?? 0}
                </span>
              </div>

              {project.roles && project.roles.length > 0 && (
                <section className="mt-6 rounded-2xl border border-border bg-surface-2 p-5">
                  <h2 className="mb-3 font-semibold">Роли в команде</h2>
                  <ul className="space-y-2 text-sm">
                    {project.roles.map((role) => (
                      <li
                        key={role.id}
                        className="rounded-lg border border-border/60 px-3 py-2"
                      >
                        <p className="font-medium">{role.title}</p>
                        {role.skills && (
                          <p className="text-muted">Навыки: {role.skills}</p>
                        )}
                        <p className="text-xs text-muted">
                          Свободно {role.seats_left} из {role.slots}
                          {role.hours_per_week != null && ` · ${role.hours_per_week} ч/нед`}
                        </p>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {student && (
                <section className="mt-6 rounded-2xl border border-border bg-surface-2 p-5">
                  <h2 className="mb-3 font-semibold">Запись на проект</h2>
                  {project.my_enrollment ? (
                    <div className="space-y-3">
                      <p className="text-sm text-emerald-400">
                        Вы записаны
                        {project.my_enrollment.role_title
                          ? ` · роль: ${project.my_enrollment.role_title}`
                          : ""}
                      </p>
                      <button
                        type="button"
                        onClick={onWithdraw}
                        disabled={busy}
                        className="rounded-xl border border-red-500/40 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                      >
                        {busy ? "…" : "Отменить запись"}
                      </button>
                    </div>
                  ) : canEnroll ? (
                    <div className="space-y-3">
                      {project.roles && project.roles.length > 0 && (
                        <label className="block text-sm text-muted">
                          Роль (необязательно)
                          <select
                            value={selectedRole}
                            onChange={(e) =>
                              setSelectedRole(
                                e.target.value === "" ? "" : Number(e.target.value),
                              )
                            }
                            className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2 text-text"
                          >
                            <option value="">Любая свободная</option>
                            {project.roles
                              .filter((r) => r.seats_left > 0)
                              .map((r) => (
                                <option key={r.id} value={r.id}>
                                  {r.title} ({r.seats_left} мест)
                                </option>
                              ))}
                          </select>
                        </label>
                      )}
                      <button
                        type="button"
                        onClick={onEnroll}
                        disabled={busy}
                        className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                      >
                        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                        Записаться
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm text-muted">Нет свободных мест в команде.</p>
                  )}
                </section>
              )}

              {project.description && (
                <p className="mt-4 text-muted">{project.description}</p>
              )}
              {project.spec_markdown && (
                <div className="mt-8 rounded-2xl border border-border bg-surface-2 p-6">
                  <h2 className="mb-4 font-semibold">Техническое задание</h2>
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-text">
                    {project.spec_markdown}
                  </pre>
                </div>
              )}
            </article>
          )}
        </main>
      </div>
    </AuthGuard>
  );
}
