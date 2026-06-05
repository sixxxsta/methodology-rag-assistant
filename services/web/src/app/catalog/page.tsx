"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";
import {
  deleteCatalogProject,
  fetchMyEnrollments,
  fetchProjectCatalog,
  fetchProjectRecommendations,
  fetchStudentProfile,
  saveStudentProfile,
} from "@/lib/api";
import { canUseEdAgent, getUser, isAdmin, isStudent } from "@/lib/auth";
import { ArrowLeft, BookOpen, Search, Sparkles, Trash2 } from "lucide-react";

export default function CatalogPage() {
  const [items, setItems] = useState<
    Awaited<ReturnType<typeof fetchProjectCatalog>>["items"]
  >([]);
  const [filter, setFilter] = useState("");
  const [appliedFilter, setAppliedFilter] = useState("");
  const [myProjects, setMyProjects] = useState<
    Awaited<ReturnType<typeof fetchMyEnrollments>>["items"]
  >([]);
  const [recommendations, setRecommendations] = useState<
    Awaited<ReturnType<typeof fetchProjectRecommendations>>["items"]
  >([]);
  const [profileSkills, setProfileSkills] = useState("");
  const [profileNotes, setProfileNotes] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileMsg, setProfileMsg] = useState("");
  const [error, setError] = useState("");
  const user = getUser();
  const student = isStudent(user);
  const moderation = isAdmin(user);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const data = await fetchProjectCatalog(appliedFilter || undefined);
      setItems(data.items);
      if (student) {
        const mine = await fetchMyEnrollments();
        setMyProjects(mine.items);
        const [profile, rec] = await Promise.all([
          fetchStudentProfile().catch(() => ({ profile: null })),
          fetchProjectRecommendations(8).catch(() => ({ items: [] })),
        ]);
        if (profile.profile) {
          setProfileSkills(profile.profile.skills);
          setProfileNotes(profile.profile.notes || "");
        }
        setRecommendations(rec.items);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }, [appliedFilter, student]);

  useEffect(() => {
    load();
  }, [load]);

  const backHref = canUseEdAgent(getUser()) ? "/dashboard/projects" : "/";
  const backLabel = canUseEdAgent(getUser()) ? "К проектам" : "К чату";

  function applyFilter(e: React.FormEvent) {
    e.preventDefault();
    setAppliedFilter(filter.trim());
  }

  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar className="md:sticky md:top-0 md:h-screen" />
        <main className="flex-1 p-6 md:p-10">
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <Link
              href={backHref}
              className="flex items-center gap-2 text-sm text-muted hover:text-accent"
            >
              <ArrowLeft className="h-4 w-4" />
              {backLabel}
            </Link>
            <h1 className="flex items-center gap-2 text-2xl font-bold">
              <BookOpen className="h-7 w-7 text-accent" />
              Каталог проектов
            </h1>
          </div>

          <p className="mb-4 text-sm text-muted">
            Опубликованные проекты для студенческих команд. В одном семестре команда может
            взять только один проект.{" "}
            {student && (
              <>
                <Link href="/teams" className="text-accent hover:underline">
                  Соберите команду
                </Link>{" "}
                — проект выбирает только лидер.
              </>
            )}
          </p>

          <form onSubmit={applyFilter} className="mb-6 flex flex-wrap gap-2">
            <label className="flex min-w-[240px] flex-1 items-center gap-2 rounded-xl border border-border bg-surface-2 px-3 py-2">
              <Search className="h-4 w-4 shrink-0 text-muted" />
              <input
                type="text"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Фильтр по компетенциям: Python, Agile…"
                className="w-full bg-transparent text-sm outline-none"
              />
            </label>
            <button
              type="submit"
              className="rounded-xl border border-border px-4 py-2 text-sm hover:border-accent"
            >
              Найти
            </button>
            {appliedFilter && (
              <button
                type="button"
                onClick={() => {
                  setFilter("");
                  setAppliedFilter("");
                }}
                className="rounded-xl px-4 py-2 text-sm text-muted hover:text-text"
              >
                Сбросить
              </button>
            )}
          </form>

          {student && (
            <section className="mb-8 rounded-2xl border border-border bg-surface-2 p-5">
              <h2 className="mb-2 flex items-center gap-2 font-semibold">
                <Sparkles className="h-5 w-5 text-accent" />
                Мой профиль навыков
              </h2>
              <p className="mb-3 text-sm text-muted">
                Укажите навыки через запятую — подбор проектов учтёт совпадение с ТЗ.
              </p>
              <form
                className="space-y-3"
                onSubmit={async (e) => {
                  e.preventDefault();
                  setProfileBusy(true);
                  setProfileMsg("");
                  try {
                    await saveStudentProfile(profileSkills, profileNotes || undefined);
                    setProfileMsg("Профиль сохранён.");
                    const rec = await fetchProjectRecommendations(8);
                    setRecommendations(rec.items);
                  } catch (err) {
                    setProfileMsg(err instanceof Error ? err.message : "Ошибка");
                  } finally {
                    setProfileBusy(false);
                  }
                }}
              >
                <input
                  type="text"
                  value={profileSkills}
                  onChange={(e) => setProfileSkills(e.target.value)}
                  placeholder="Python, SQL, Agile…"
                  className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm"
                />
                <textarea
                  value={profileNotes}
                  onChange={(e) => setProfileNotes(e.target.value)}
                  placeholder="Заметки (необязательно)"
                  rows={2}
                  className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm"
                />
                <button
                  type="submit"
                  disabled={profileBusy || !profileSkills.trim()}
                  className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  {profileBusy ? "Сохранение…" : "Сохранить"}
                </button>
              </form>
              {profileMsg && <p className="mt-2 text-sm text-muted">{profileMsg}</p>}
            </section>
          )}

          {student && recommendations.length > 0 && (
            <section className="mb-8 rounded-2xl border border-accent/30 bg-surface-2 p-5">
              <h2 className="mb-3 font-semibold">Рекомендованные проекты</h2>
              <ul className="space-y-2 text-sm">
                {recommendations.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-baseline gap-2">
                    <Link href={`/catalog/${p.id}`} className="font-medium text-accent hover:underline">
                      {p.title}
                    </Link>
                    {p.match_score != null && (
                      <span className="text-xs text-muted">совпадение {p.match_score}%</span>
                    )}
                    {p.matched_skills && p.matched_skills.length > 0 && (
                      <span className="text-xs text-muted">
                        ({p.matched_skills.join(", ")})
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {student && myProjects.length > 0 && (
            <section className="mb-8 rounded-2xl border border-accent/30 bg-surface-2 p-5">
              <h2 className="mb-3 font-semibold">Мои проекты</h2>
              <ul className="space-y-2 text-sm">
                {myProjects.map((p) => (
                  <li key={p.id}>
                    <Link href={`/catalog/${p.project_id}`} className="text-accent hover:underline">
                      {p.project_title}
                    </Link>
                    {p.role_title && (
                      <span className="text-muted"> · {p.role_title}</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {loading && <p className="text-muted">Загрузка…</p>}
          {error && <p className="text-sm text-red-400">{error}</p>}

          {!loading && items.length === 0 && (
            <p className="rounded-lg border border-border bg-surface-2 px-4 py-6 text-sm text-muted">
              {appliedFilter
                ? "Нет проектов с такими компетенциями."
                : "Каталог пока пуст. Куратор публикует проекты после согласования с партнёром."}
            </p>
          )}

          <ul className="grid gap-4 sm:grid-cols-2">
            {items.map((item) => (
              <li
                key={item.id}
                className="rounded-2xl border border-border bg-surface-2 p-5 transition hover:border-accent/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <Link href={`/catalog/${item.id}`} className="min-w-0 flex-1">
                    <h2 className="font-semibold leading-snug hover:text-accent">{item.title}</h2>
                  </Link>
                  {moderation && (
                    <button
                      type="button"
                      title="Удалить из каталога"
                      disabled={busyId === item.id}
                      onClick={async () => {
                        if (
                          !window.confirm(
                            `Удалить проект «${item.title}» из каталога? Это действие нельзя отменить.`,
                          )
                        ) {
                          return;
                        }
                        setBusyId(item.id);
                        setError("");
                        try {
                          await deleteCatalogProject(item.id);
                          await load();
                        } catch (e) {
                          setError(e instanceof Error ? e.message : "Ошибка удаления");
                        } finally {
                          setBusyId(null);
                        }
                      }}
                      className="shrink-0 rounded-lg border border-red-500/40 p-2 text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <Link href={`/catalog/${item.id}`} className="block">
                  {item.company_name && (
                    <p className="mt-1 text-sm text-accent">{item.company_name}</p>
                  )}
                  {item.cycle_name && (
                    <p className="mt-1 text-xs text-muted">Цикл: {item.cycle_name}</p>
                  )}
                  {item.description && (
                    <p className="mt-2 text-sm text-muted line-clamp-4">{item.description}</p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
                    {item.team_member_size != null && (
                      <span>До {Math.min(item.team_member_size, 5)} чел. в команде</span>
                    )}
                    {item.duration_weeks != null && (
                      <span>Срок: {item.duration_weeks} нед.</span>
                    )}
                    {item.max_teams != null && (
                      <span>
                        Команд: {item.teams_claimed ?? 0}/{item.max_teams}
                        {(item.teams_left ?? 0) > 0
                          ? ` · свободно ${item.teams_left}`
                          : " · занято"}
                      </span>
                    )}
                  </div>
                  {item.competencies && (
                    <p className="mt-2 text-xs text-muted">
                      Компетенции: {item.competencies}
                    </p>
                  )}
                  <p className="mt-3 text-xs text-accent">Открыть ТЗ →</p>
                </Link>
              </li>
            ))}
          </ul>
        </main>
      </div>
    </AuthGuard>
  );
}
