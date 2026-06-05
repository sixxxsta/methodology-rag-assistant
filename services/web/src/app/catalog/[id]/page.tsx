"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";
import {
  claimProjectForTeam,
  deleteCatalogProject,
  fetchCatalogProject,
  startProjectInterview,
  submitProjectInterview,
  withdrawTeamProjectClaim,
  type CatalogProjectDetail,
} from "@/lib/api";
import { getUser, isAdmin, isStudent } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { ArrowLeft, BookOpen, Loader2, Trash2 } from "lucide-react";

type Props = { params: Promise<{ id: string }> };

export default function CatalogProjectPage({ params }: Props) {
  const [projectId, setProjectId] = useState<number | null>(null);
  const [project, setProject] = useState<CatalogProjectDetail | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [interviewAnswers, setInterviewAnswers] = useState<string[]>([]);
  const [showInterview, setShowInterview] = useState(false);
  const user = getUser();
  const student = isStudent(user);
  const moderation = isAdmin(user);
  const router = useRouter();

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

  useEffect(() => {
    if (project?.can_submit_interview && project.interview_questions?.length) {
      setShowInterview(true);
      setInterviewAnswers((prev) => {
        if (prev.length === project.interview_questions!.length) return prev;
        return project.interview_questions!.map((_, i) => prev[i] ?? "");
      });
    }
  }, [project?.can_submit_interview, project?.interview_questions]);

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

  async function onStartInterview() {
    if (!projectId) return;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const res = await startProjectInterview(projectId);
      setInterviewAnswers(res.questions.map(() => ""));
      setShowInterview(true);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmitInterview() {
    if (!projectId) return;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const res = await submitProjectInterview(projectId, interviewAnswers);
      if (res.awaiting_curator) {
        setInfo("Ответы отправлены. Ожидайте проверки куратором.");
        setShowInterview(false);
      } else if (res.passed) {
        setInfo(res.feedback);
        setShowInterview(false);
      } else {
        setError(res.feedback);
        setShowInterview(false);
      }
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
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <h1 className="flex items-start gap-2 text-2xl font-bold leading-snug">
                  <BookOpen className="mt-1 h-7 w-7 shrink-0 text-accent" />
                  {project.title}
                </h1>
                {moderation && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={async () => {
                      if (
                        !window.confirm(
                          `Удалить проект «${project.title}» из каталога? Это действие нельзя отменить.`,
                        )
                      ) {
                        return;
                      }
                      setBusy(true);
                      setError("");
                      try {
                        await deleteCatalogProject(projectId!);
                        router.push("/catalog");
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Ошибка удаления");
                        setBusy(false);
                      }
                    }}
                    className="inline-flex items-center gap-2 rounded-xl border border-red-500/40 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                  >
                    <Trash2 className="h-4 w-4" />
                    Удалить из каталога
                  </button>
                )}
              </div>
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
                {project.interview_required && (
                  <span className="text-amber-400">Требуется собеседование</span>
                )}
              </div>

              {(project.claimed_teams?.length ?? 0) > 0 && (
                <section className="mt-6 rounded-2xl border border-border bg-surface-2 p-5">
                  <h2 className="mb-3 font-semibold">Команды на проекте</h2>
                  <ul className="space-y-2 text-sm">
                    {project.claimed_teams!.map((t) => (
                      <li
                        key={t.claim_id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/60 px-3 py-2"
                      >
                        <span className="font-medium">{t.team_name}</span>
                        <span className="text-xs text-muted">
                          лидер {t.leader_fio || t.leader_email} · {t.member_count} чел.
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

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
                          Отменить выбор может только лидер:{" "}
                      {project.my_team?.leader_fio || project.my_team?.leader_email}
                        </p>
                      )}
                    </div>
                  ) : otherProjectClaim ? (
                    <p className="text-sm text-muted">
                      Команда уже выбрала другой проект:{" "}
                      {project.my_team_claim?.project_title || `#${project.my_team_claim?.project_id}`}.
                      Сначала отмените его (лидер).
                    </p>
                  ) : project.semester_claim_blocked && project.semester_claim_block_reason ? (
                    <p className="text-sm text-amber-400">{project.semester_claim_block_reason}</p>
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
                      {project.interview_required && !project.interview_passed && (
                        <p className="text-sm text-amber-300">
                          Перед выбором проекта лидер команды проходит короткое собеседование.
                        </p>
                      )}
                      {project.awaiting_curator_review && (
                        <p className="text-sm text-amber-300">
                          Ответы на собеседование на проверке у куратора.
                        </p>
                      )}
                      {project.interview_status === "passed" && (
                        <p className="text-sm text-emerald-400">
                          Собеседование одобрено куратором. Можно выбрать проект.
                        </p>
                      )}
                      {project.interview_feedback && project.interview_status === "failed" && (
                        <p className="text-sm text-red-400">{project.interview_feedback}</p>
                      )}
                      {(showInterview || project.can_submit_interview) &&
                        (project.interview_questions?.length ?? 0) > 0 && (
                          <div className="space-y-3 rounded-xl border border-border/60 bg-surface p-4">
                            <p className="text-sm font-medium">Вопросы собеседования</p>
                            {project.interview_questions!.map((q, i) => (
                              <label key={i} className="block text-xs text-muted">
                                {i + 1}. {q}
                                <textarea
                                  value={interviewAnswers[i] ?? ""}
                                  onChange={(e) => {
                                    const next = [...interviewAnswers];
                                    next[i] = e.target.value;
                                    setInterviewAnswers(next);
                                  }}
                                  rows={3}
                                  className="mt-1 w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text"
                                />
                              </label>
                            ))}
                            <button
                              type="button"
                              onClick={onSubmitInterview}
                              disabled={busy}
                              className="rounded-xl bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
                            >
                              {busy ? "…" : "Отправить ответы"}
                            </button>
                          </div>
                        )}
                      {project.interview_required &&
                        !project.interview_passed &&
                        project.can_start_interview &&
                        !showInterview &&
                        !project.can_submit_interview && (
                          <button
                            type="button"
                            onClick={onStartInterview}
                            disabled={busy}
                            className="inline-flex items-center gap-2 rounded-xl border border-amber-500/50 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-200 disabled:opacity-50"
                          >
                            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                            Пройти собеседование
                          </button>
                        )}
                      {(!project.interview_required || project.interview_passed) && (
                        <button
                          type="button"
                          onClick={onClaim}
                          disabled={busy || teamsFull || !project.can_claim_as_leader}
                          className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                        >
                          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                          Выбрать проект для команды
                        </button>
                      )}
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
                      {project.interview_required &&
                        !project.interview_passed &&
                        isLeader &&
                        (project.team_members_short ?? 0) === 0 &&
                        !teamsFull && (
                          <p className="text-xs text-muted">
                            После успешного собеседования станет доступна кнопка выбора проекта.
                          </p>
                        )}
                    </div>
                  ) : (
                    <p className="text-sm text-muted">
                      Проект выбирает лидер команды (
                      {project.my_team?.leader_fio || project.my_team?.leader_email}).
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
