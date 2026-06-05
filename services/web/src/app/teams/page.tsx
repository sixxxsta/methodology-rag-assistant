"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";
import {
  createStudentTeam,
  fetchMyTeam,
  joinStudentTeam,
  leaveStudentTeam,
  transferTeamLeadership,
  type StudentTeam,
} from "@/lib/api";
import { getUser, isStudent } from "@/lib/auth";
import { ArrowLeft, Copy, Users } from "lucide-react";

export default function TeamsPage() {
  const [team, setTeam] = useState<StudentTeam | null>(null);
  const [inviteInput, setInviteInput] = useState("");
  const [newTeamName, setNewTeamName] = useState("");
  const [transferEmail, setTransferEmail] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const student = isStudent(getUser());

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const r = await fetchMyTeam();
      setTeam(r.team);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (student) load();
    else setLoading(false);
  }, [load, student]);

  async function copyCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      setInfo("Код скопирован");
    } catch {
      setInfo(code);
    }
  }

  if (!student) {
    return (
      <AuthGuard>
        <div className="p-10 text-muted">Страница только для студентов.</div>
      </AuthGuard>
    );
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

          <h1 className="mb-2 flex items-center gap-2 text-2xl font-bold">
            <Users className="h-7 w-7 text-accent" />
            Моя команда
          </h1>
          <p className="mb-6 text-sm text-muted">
            Объединитесь с одногруппниками (до 5 человек, минимум 3 для выбора). В одном
            семестре (цикле партнёрства) команда может взять только один проект. Выбор делает
            лидер.
          </p>

          {loading && <p className="text-muted">Загрузка…</p>}
          {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
          {info && (
            <p className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
              {info}
            </p>
          )}

          {!loading && !team && (
            <div className="grid max-w-lg gap-6">
              <section className="rounded-2xl border border-border bg-surface-2 p-5">
                <h2 className="mb-3 font-semibold">Создать команду</h2>
                <input
                  type="text"
                  placeholder="Название (необязательно)"
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  className="mb-3 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    setError("");
                    try {
                      const r = await createStudentTeam(newTeamName.trim() || undefined);
                      setTeam(r.team);
                      setInfo("Команда создана — вы лидер");
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Ошибка");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  Создать (я лидер)
                </button>
              </section>

              <section className="rounded-2xl border border-border bg-surface-2 p-5">
                <h2 className="mb-3 font-semibold">Вступить по коду</h2>
                <input
                  type="text"
                  placeholder="Код приглашения"
                  value={inviteInput}
                  onChange={(e) => setInviteInput(e.target.value)}
                  className="mb-3 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm uppercase"
                />
                <button
                  type="button"
                  disabled={busy || !inviteInput.trim()}
                  onClick={async () => {
                    setBusy(true);
                    setError("");
                    try {
                      const r = await joinStudentTeam(inviteInput);
                      setTeam(r.team);
                      setInfo("Вы в команде");
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Ошибка");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="rounded-xl border border-accent px-4 py-2 text-sm text-accent disabled:opacity-50"
                >
                  Вступить
                </button>
              </section>
            </div>
          )}

          {team && (
            <section className="max-w-lg rounded-2xl border border-border bg-surface-2 p-6 shadow-sm">
              <h2 className="text-xl font-bold text-text">{team.name || "Команда"}</h2>
              <div className="mt-4 rounded-xl border border-accent/25 bg-accent/5 px-4 py-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Лидер</p>
                <p className="mt-1 text-lg font-semibold text-text">
                  {team.leader_fio || team.leader_email}
                  {team.is_leader ? (
                    <span className="ml-2 text-sm font-normal text-accent">(вы)</span>
                  ) : null}
                </p>
              </div>
              <p className="mt-4 text-base text-text">
                Участников:{" "}
                <span className="font-semibold">
                  {team.member_count}/5
                </span>
              </p>
              {team.is_leader && (
                <div className="mt-3 flex items-center gap-2">
                  <span className="rounded-lg bg-surface px-3 py-2 font-mono text-sm tracking-widest">
                    {team.invite_code}
                  </span>
                  <button
                    type="button"
                    onClick={() => copyCode(team.invite_code)}
                    className="rounded-lg border border-border p-2 hover:border-accent"
                    title="Скопировать код"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                </div>
              )}

              <div className="mt-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                  Участники
                </p>
                <ul className="space-y-2">
                  {team.members.map((m) => (
                    <li
                      key={m.student_email}
                      className="flex items-center justify-between rounded-xl border border-border bg-surface px-4 py-3"
                    >
                      <span className="text-base font-medium text-text">
                        {m.fio || m.student_email}
                      </span>
                      {m.is_leader ? (
                        <span className="rounded-full bg-accent/15 px-2.5 py-0.5 text-xs font-medium text-accent">
                          лидер
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>

              {team.is_leader && team.member_count > 1 && (
                <div className="mt-4 border-t border-border pt-4">
                  <label className="block text-sm text-muted">
                    Передать лидерство
                    <input
                      type="email"
                      value={transferEmail}
                      onChange={(e) => setTransferEmail(e.target.value)}
                      className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm"
                      placeholder="email участника"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={busy || !transferEmail.trim()}
                    className="mt-2 text-sm text-accent hover:underline disabled:opacity-50"
                    onClick={async () => {
                      setBusy(true);
                      try {
                        const r = await transferTeamLeadership(transferEmail);
                        setTeam(r.team);
                        setInfo("Лидерство передано");
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Ошибка");
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Передать
                  </button>
                </div>
              )}

              <button
                type="button"
                disabled={busy}
                className="mt-6 rounded-xl border border-red-500/40 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10"
                onClick={async () => {
                  if (!window.confirm("Выйти из команды?")) return;
                  setBusy(true);
                  try {
                    await leaveStudentTeam();
                    setTeam(null);
                    setInfo("Вы вышли из команды");
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Ошибка");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Покинуть команду
              </button>
            </section>
          )}
        </main>
      </div>
    </AuthGuard>
  );
}
