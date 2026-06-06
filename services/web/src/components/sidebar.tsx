"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import Link from "next/link";
import {
  ClipboardList,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Settings,
  Sparkles,
  UserPlus,
  Users,
} from "lucide-react";
import { clearSession, getUser, isAdmin, canUseEdAgent, isStudent, roleLabel } from "@/lib/auth";
import { deleteAccount } from "@/lib/api";
import { useRouter } from "next/navigation";
import clsx from "clsx";

type Props = {
  onNewChat?: () => void;
  className?: string;
};

function EdLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="rounded-md px-2 py-1.5 text-muted transition hover:bg-surface-2 hover:text-accent"
    >
      {children}
    </Link>
  );
}

export function Sidebar({ onNewChat, className }: Props) {
  const router = useRouter();
  const user = getUser();
  const edAgent = canUseEdAgent(user);
  const student = isStudent(user);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePwd, setDeletePwd] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  async function onConfirmDeleteAccount() {
    if (!deletePwd.trim()) {
      setDeleteError("Введите пароль");
      return;
    }
    setDeleteBusy(true);
    setDeleteError("");
    try {
      await deleteAccount(deletePwd);
      clearSession();
      router.push("/login");
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Не удалось удалить аккаунт");
    } finally {
      setDeleteBusy(false);
    }
  }

  function logout() {
    clearSession();
    router.push("/login");
  }

  return (
    <>
      <aside
        className={clsx(
          "flex w-full flex-col gap-5 border-border bg-surface p-5 md:h-full md:w-72 md:shrink-0 md:border-r md:overflow-y-auto",
          className,
        )}
      >
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent/15 text-lg font-bold text-accent">
            ◇
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight">Методолог</h1>
            <p className="text-sm text-muted leading-snug">Ментор по Agile, Scrum, DevOps</p>
          </div>
        </div>

        {user && (
          <div className="rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm text-muted">
            <span className="text-text">{user.fio?.trim() || user.email}</span>
            <span className="ml-2 rounded-md bg-accent/20 px-1.5 py-0.5 text-xs text-accent">
              {roleLabel(user.role)}
            </span>
          </div>
        )}

        <div className="rounded-xl border border-border bg-surface-2 p-4 text-sm text-muted">
          <p className="mb-2 flex items-center gap-2 font-medium text-text">
            <Sparkles className="h-4 w-4 text-accent" />
            Подсказка
          </p>
          <ul className="list-disc space-y-1 pl-4">
            <li>Ответы только из базы знаний</li>
            <li>Источники под каждым ответом</li>
            <li>Спросите про роли, спринт, ГОСТ</li>
          </ul>
        </div>

        <p className="text-xs text-muted">
          Канал куратора:{" "}
          <a
            href="https://t.me/+Xqp0SQjGmVA1ODgy"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            Telegram
          </a>
        </p>

        <div className="mt-auto flex flex-col gap-2">
          {edAgent && (
            <>
              <p className="px-1 text-xs font-medium uppercase tracking-wide text-muted">EdAgent</p>
              <Link
                href="/dashboard"
                className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm transition hover:border-accent hover:bg-surface-2"
              >
                <LayoutDashboard className="h-4 w-4 shrink-0" />
                Обзор фаз
              </Link>
              <nav className="flex flex-col gap-0.5 pl-1 text-sm">
                <EdLink href="/dashboard/competencies">1. Компетенции</EdLink>
                <EdLink href="/dashboard/companies">2. Компании</EdLink>
                <EdLink href="/dashboard/communications">3. Коммуникации</EdLink>
                <EdLink href="/dashboard/outreach">4. Outreach</EdLink>
                <EdLink href="/dashboard/projects">5. Проекты</EdLink>
              </nav>
              <Link
                href="/dashboard/interviews"
                className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-200 transition hover:border-amber-500/50"
              >
                <ClipboardList className="h-4 w-4 shrink-0" />
                Собеседования команд
              </Link>
            </>
          )}
          <Link
            href="/catalog"
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm transition hover:border-accent hover:bg-surface-2"
          >
            Каталог проектов
          </Link>
          {student && (
            <Link
              href="/teams"
              className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm transition hover:border-accent hover:bg-surface-2"
            >
              <Users className="h-4 w-4" />
              Моя команда
            </Link>
          )}
          {onNewChat && (
            <button
              type="button"
              onClick={onNewChat}
              className="flex items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm transition hover:border-accent hover:bg-surface-2"
            >
              <MessageSquare className="h-4 w-4" />
              Новый диалог
            </button>
          )}
          {isAdmin(user) && (
            <>
              <Link
                href="/admin#curators"
                className="flex items-center justify-center gap-2 rounded-xl border border-accent/40 bg-accent/10 px-4 py-2.5 text-sm font-medium text-accent transition hover:bg-accent/15"
              >
                <UserPlus className="h-4 w-4" />
                Добавить куратора
              </Link>
              <Link
                href="/admin"
                className="flex items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm transition hover:border-accent hover:bg-surface-2"
              >
                <Settings className="h-4 w-4" />
                Админка
              </Link>
            </>
          )}
          {student && (
            <button
              type="button"
              onClick={() => {
                setDeletePwd("");
                setDeleteError("");
                setDeleteOpen(true);
              }}
              className="rounded-xl border border-red-500/30 px-4 py-2 text-xs text-red-400 transition hover:bg-red-500/10"
            >
              Удалить аккаунт
            </button>
          )}
          <button
            type="button"
            onClick={logout}
            className="flex items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm text-muted transition hover:border-red-500/50 hover:text-red-400"
          >
            <LogOut className="h-4 w-4" />
            Выйти
          </button>
        </div>
      </aside>

      {deleteOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-2xl border border-border bg-surface-2 p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-text">Удаление аккаунта</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              Вы действительно хотите удалить аккаунт? Это действие необратимо.
            </p>
            <label className="mt-4 block text-sm text-muted">
              Пароль для подтверждения
              <input
                type="password"
                value={deletePwd}
                onChange={(e) => setDeletePwd(e.target.value)}
                className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text"
                autoFocus
              />
            </label>
            {deleteError && <p className="mt-2 text-sm text-red-400">{deleteError}</p>}
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button
                type="button"
                disabled={deleteBusy}
                onClick={() => setDeleteOpen(false)}
                className="rounded-xl border border-border px-4 py-2 text-sm text-text hover:border-accent"
              >
                Нет
              </button>
              <button
                type="button"
                disabled={deleteBusy}
                onClick={onConfirmDeleteAccount}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50"
              >
                {deleteBusy ? "Удаление…" : "Да"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
