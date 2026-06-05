"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login, register } from "@/lib/api";
import { getToken, setSession } from "@/lib/auth";
import clsx from "clsx";

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [fio, setFio] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) router.replace("/");
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data =
        tab === "login"
          ? await login(email, password)
          : await register(email, password, fio);
      setSession(data.token, data.user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md glass rounded-2xl p-8 shadow-xl shadow-black/30">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-accent/15 text-xl font-bold text-accent">
            ◇
          </div>
          <h1 className="text-2xl font-bold">Методолог</h1>
          <p className="mt-1 text-sm text-muted">
            {tab === "login"
              ? "Войдите по выданным учётным данным"
              : "Регистрация доступна только ученикам"}
          </p>
        </div>

        <div className="mb-6 flex gap-2 rounded-xl bg-surface-2 p-1">
          {(["login", "register"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => {
                setTab(t);
                setError("");
              }}
              className={clsx(
                "flex-1 rounded-lg py-2 text-sm font-medium transition",
                tab === t ? "bg-accent/20 text-accent" : "text-muted hover:text-text",
              )}
            >
              {t === "login" ? "Вход" : "Регистрация"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-4">
          {tab === "register" && (
            <label className="block text-sm text-muted">
              ФИО
              <input
                type="text"
                required
                minLength={2}
                autoComplete="name"
                value={fio}
                onChange={(e) => setFio(e.target.value)}
                className="mt-1.5 w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-text outline-none focus:border-accent"
              />
            </label>
          )}
          <label className="block text-sm text-muted">
            Email
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-text outline-none focus:border-accent"
            />
          </label>
          <label className="block text-sm text-muted">
            Пароль {tab === "register" && "(мин. 6 символов)"}
            <input
              type="password"
              required
              minLength={6}
              autoComplete={tab === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-text outline-none focus:border-accent"
            />
          </label>

          {error && (
            <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-accent py-3 font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Подождите…" : tab === "login" ? "Войти" : "Зарегистрироваться"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-muted">
          <Link href="https://t.me/+Xqp0SQjGmVA1ODgy" className="text-accent hover:underline">
            Канал куратора
          </Link>
        </p>
      </div>
    </div>
  );
}
