"use client";

import { useEffect, useState } from "react";
import { UserPlus } from "lucide-react";
import { createStaffUser } from "@/lib/api";
import clsx from "clsx";

type Props = {
  onSuccess?: (message: string) => void;
  onError?: (message: string) => void;
  className?: string;
  defaultOpen?: boolean;
  showToggle?: boolean;
};

export function AddCuratorForm({
  onSuccess,
  onError,
  className,
  defaultOpen = false,
  showToggle = true,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [staffEmail, setStaffEmail] = useState("");
  const [staffFio, setStaffFio] = useState("");
  const [staffPassword, setStaffPassword] = useState("");
  const [staffRole, setStaffRole] = useState<"curator" | "admin">("curator");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hash === "#curators") {
      setOpen(true);
    }
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await createStaffUser({
        email: staffEmail.trim(),
        fio: staffFio.trim(),
        password: staffPassword,
        role: staffRole,
      });
      const msg = `Создан аккаунт ${res.user.fio || res.user.email} (${staffRole === "curator" ? "куратор" : "модерация"})`;
      onSuccess?.(msg);
      setStaffEmail("");
      setStaffFio("");
      setStaffPassword("");
      setStaffRole("curator");
      if (showToggle) setOpen(false);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Ошибка создания аккаунта");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={className}>
      {showToggle && !open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
        >
          <UserPlus className="h-4 w-4" />
          Добавить куратора
        </button>
      )}

      {(open || !showToggle) && (
        <div className={clsx(showToggle && "mt-4")}>
          {showToggle && (
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="font-semibold text-text">Новый куратор</h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-xs text-muted hover:text-text"
              >
                Скрыть
              </button>
            </div>
          )}
          <form onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm text-muted sm:col-span-2">
              ФИО
              <input
                type="text"
                required
                minLength={2}
                value={staffFio}
                onChange={(e) => setStaffFio(e.target.value)}
                placeholder="Иванов Иван Иванович"
                className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent"
              />
            </label>
            <label className="block text-sm text-muted sm:col-span-2">
              Email
              <input
                type="email"
                required
                value={staffEmail}
                onChange={(e) => setStaffEmail(e.target.value)}
                placeholder="curator@example.com"
                className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent"
              />
            </label>
            <label className="block text-sm text-muted">
              Пароль (мин. 6)
              <input
                type="password"
                required
                minLength={6}
                value={staffPassword}
                onChange={(e) => setStaffPassword(e.target.value)}
                className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent"
              />
            </label>
            <label className="block text-sm text-muted">
              Роль
              <select
                value={staffRole}
                onChange={(e) => setStaffRole(e.target.value as "curator" | "admin")}
                className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent"
              >
                <option value="curator">Куратор</option>
                <option value="admin">Модерация</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 sm:col-span-2 sm:w-fit"
            >
              <UserPlus className="h-4 w-4" />
              {busy ? "Создание…" : "Добавить куратора"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
