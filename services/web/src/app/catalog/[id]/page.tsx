"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";
import {
  claimProjectForTeam,
  fetchCatalogProject,
  withdrawTeamProjectClaim,
  type CatalogProjectDetail,
} from "@/lib/api";
import { getUser, isStudent } from "@/lib/auth";
import { ArrowLeft, BookOpen, Loader2 } from "lucide-react";

type Props = { params: Promise<{ id: string }> };

export default function CatalogProjectPage({ params }: Props) {
  const [projectId, setProjectId] = useState<number | null>(null);
  const [project, setProject] = useState<CatalogProjectDetail | null>(null);
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

  const hasClaim =
    project?.my_team_claim?.project_id === projectId &&
    project?.my_team_claim?.status === "active";
  const teamsFull = (project?.teams_left ?? 0) <= 0;
  const isLeader = project?.my_team?.is_leader === true;
  const hasTeam = !!project?.my_team;
  const otherProjectClaim =
    project?.my_team_claim &&
    project.my_team_claim.project_id !== projectId &&
    project.my_team_claim.status === "active";

  async function onClaim() {
    if (!projectId) return;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      await claimProjectForTeam(projectId);
      setInfo("Проект выбран для вашей команды");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
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
      await withdrawTeamProjectClaim(projectId);
      setInfo("Выбор проекта отменён");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

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
                {project.team_member_size != null && (
                  <span>Размер команды: до {Math.min(project.team_member_size, 5)} чел.</span>
                )}
                {project.duration_weeks != null && (
                  <span>Срок: {project.duration_weeks} нед.</span>
                )}
                <span>
                  Команд на проект: {project.teams_claimed ?? 0}/{project.max_teams ?? "—"}
                  {(project.teams_left ?? 0) > 0
                    ? ` · свободно ${project.teams_left}`
                    : " · мест нет"}
                </span>
              </div>

              {student && (
                <section className="mt-6 rounded-2xl border border-border bg-surface-2 p-5">
                  <h2 className="mb-3 font-semibold">Выбор проекта командой</h2>
                  {!hasTeam ? (
                    <p className="text-sm text-muted">
                      Сначала{" "}
                      <Link href="/teams" className="text-accent hover:underline">
                        создайте команду или вступите по коду
                      </Link>
                      .
                    </p>
                  ) : hasClaim ? (
                    <div className="space-y-3">
                      <p className="text-sm text-emerald-400">
                        Ваша команда выбрала этот проект
                        {project.my_team?.name ? ` («${project.my_team.name}»)` : ""}.
                      </p>
                      {isLeader && (
                        <button
                          type="button"
                          onClick={onWithdraw}
                          disabled={busy}
                          className="rounded-xl border border-red-500/40 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                        >
                          {busy ? "…" : "Отменить выбор (лидер)"}
                        </button>
                      )}
                      {!isLeader && (
                        <p className="text-xs text-muted">
                          Отменить выбор может только лидер: {project.my_team?.leader_email}
                        </p>
                      )}
                    </div>
                  ) : otherProjectClaim ? (
                    <p className="text-sm text-muted">
                      Команда уже выбрала другой проект:{" "}
                      {project.my_team_claim?.project_title || `#${project.my_team_claim?.project_id}`}.
                      Сначала отмените его (лидер).
                    </p>
                  ) : isLeader ? (
                    <div className="space-y-3">
                      <p className="text-sm text-muted">
                        Участников в команде: {project.team_member_count ?? project.my_team?.member_count ?? 0}
                        /5 (минимум {project.min_team_members_to_claim ?? 3} для выбора проекта).
                      </p>
                      {(project.team_members_short ?? 0) > 0 && (
                        <p className="text-xs text-amber-400">
                          Не хватает {project.team_members_short} участник(ов). Пригласите в{" "}
                          <Link href="/teams" className="text-accent hover:underline">
                            команду
                          </Link>
                          .
                        </p>
                      )}
                      <button
                        type="button"
                        onClick={onClaim}
                        disabled={busy || teamsFull || !project.can_claim_as_leader}
                        className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                      >
                        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                        Выбрать проект для команды
                      </button>
                      {teamsFull && (
                        <p className="text-xs text-amber-400">
                          Все слоты команд заняты — выбрать нельзя.
                        </p>
                      )}
                      {!teamsFull &&
                        (project.team_members_short ?? 0) > 0 &&
                        isLeader && (
                          <p className="text-xs text-muted">
                            Кнопка станет доступна при {project.min_team_members_to_claim ?? 3}{" "}
                            участниках в команде.
                          </p>
                        )}
                    </div>
                  ) : (
                    <p className="text-sm text-muted">
                      Проект выбирает лидер команды ({project.my_team?.leader_email}).
                    </p>
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
