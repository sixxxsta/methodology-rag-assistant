"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";
import {
  collectVacancies,
  fetchCompetencyMatrix,
  fetchCompetencyStats,
  seedProgramCompetencies,
} from "@/lib/api";
import { getUser, isAdmin } from "@/lib/auth";
import type { CompetencyMatrix, MatrixItem } from "@/lib/types";
import clsx from "clsx";
import { ArrowLeft, Download, Loader2, Search } from "lucide-react";

const GAP_LABELS: Record<string, string> = {
  missing_in_program: "Нет в программе",
  undertrained: "Недостаточно в программе",
  overtrained: "Избыток в программе",
  niche_program: "Ниша программы",
  aligned: "Соответствует",
};

function gapColor(type: string) {
  if (type === "aligned") return "text-emerald-400 bg-emerald-500/10";
  if (type === "missing_in_program" || type === "undertrained")
    return "text-amber-400 bg-amber-500/10";
  return "text-sky-400 bg-sky-500/10";
}

export default function CompetenciesPage() {
  const [matrix, setMatrix] = useState<CompetencyMatrix | null>(null);
  const [stats, setStats] = useState({ program: 0, industry: 0, vacancies: 0 });
  const [query, setQuery] = useState("Python разработчик");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [info, setInfo] = useState("");
  const admin = isAdmin(getUser());

  const load = useCallback(async () => {
    setError("");
    try {
      const [m, s] = await Promise.all([fetchCompetencyMatrix(), fetchCompetencyStats()]);
      setMatrix(m);
      setStats({
        program: s.program_competencies,
        industry: s.industry_competencies,
        vacancies: s.vacancies,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onCollect() {
    if (!query.trim()) return;
    setCollecting(true);
    setError("");
    try {
      const r = await collectVacancies(query.trim(), 2);
      if (r.demo_mode && r.message) setInfo(r.message);
      else setInfo("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сбора");
    } finally {
      setCollecting(false);
    }
  }

  const topGaps = matrix?.items.filter((i) => i.gap_type !== "aligned").slice(0, 15) ?? [];

  return (
    <AuthGuard>
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
            <h1 className="text-2xl font-bold">Фаза 1 — Компетенции</h1>
          </div>

          <div className="mb-6 grid gap-3 sm:grid-cols-3">
            <StatCard label="Компетенции программы" value={stats.program} />
            <StatCard label="С рынка (HH)" value={stats.industry} />
            <StatCard label="Вакансий в базе" value={stats.vacancies} />
          </div>

          {admin && (
            <section className="mb-8 rounded-2xl border border-border bg-surface-2 p-5">
              <h2 className="mb-3 flex items-center gap-2 font-semibold">
                <Search className="h-5 w-5 text-accent" />
                Сбор вакансий HeadHunter
              </h2>
              <p className="mb-4 text-sm text-muted">
                Поиск по API hh.ru, извлечение навыков из описаний (FR-1.1, FR-1.2).
              </p>
              <div className="flex flex-wrap gap-2">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Запрос, напр. аналитик данных"
                  className="min-w-[220px] flex-1 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm"
                />
                <button
                  type="button"
                  disabled={collecting || !query.trim()}
                  onClick={onCollect}
                  className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  {collecting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Собрать
                </button>
                <button
                  type="button"
                  disabled={collecting}
                  onClick={async () => {
                    setCollecting(true);
                    try {
                      await seedProgramCompetencies();
                      await load();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Ошибка");
                    } finally {
                      setCollecting(false);
                    }
                  }}
                  className="rounded-xl border border-border px-4 py-2.5 text-sm hover:bg-surface"
                >
                  Загрузить программу
                </button>
              </div>
            </section>
          )}

          {info && (
            <p className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200">
              {info}
            </p>
          )}

          {error && (
            <p className="mb-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-400">{error}</p>
          )}
          {loading && <p className="text-muted">Загрузка матрицы…</p>}

          {matrix && (
            <>
              <div className="mb-4 flex flex-wrap gap-4 text-sm">
                <span className="text-muted">
                  Всего в сравнении: <strong className="text-text">{matrix.summary.total}</strong>
                </span>
                <span className="text-amber-400">Пробелы: {matrix.summary.gaps}</span>
                <span className="text-emerald-400">Соответствие: {matrix.summary.aligned}</span>
                <span className="text-sky-400">Избыток: {matrix.summary.excess}</span>
              </div>

              <MatrixTable title="Приоритетные пробелы" rows={topGaps} empty="Соберите вакансии или все навыки в норме" />

              {matrix.items.length > 0 && (
                <div className="mt-8">
                  <MatrixTable title="Полная матрица" rows={matrix.items} />
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </AuthGuard>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2 px-4 py-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function MatrixTable({
  title,
  rows,
  empty,
}: {
  title: string;
  rows: MatrixItem[];
  empty?: string;
}) {
  return (
    <section className="rounded-2xl border border-border bg-surface-2 overflow-hidden">
      <h2 className="border-b border-border px-4 py-3 font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="p-4 text-sm text-muted">{empty ?? "Нет данных"}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="px-4 py-2">Навык</th>
                <th className="px-4 py-2">Программа (1–5)</th>
                <th className="px-4 py-2">Спрос рынка %</th>
                <th className="px-4 py-2">Статус</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name} className="border-b border-border/50 hover:bg-surface">
                  <td className="px-4 py-2 font-medium">{row.name}</td>
                  <td className="px-4 py-2">{row.program_level || "—"}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
                        <div
                          className="h-full bg-accent"
                          style={{ width: `${row.industry_demand_pct}%` }}
                        />
                      </div>
                      {row.industry_demand_pct}%
                    </div>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={clsx(
                        "rounded-md px-2 py-0.5 text-xs",
                        gapColor(row.gap_type),
                      )}
                    >
                      {GAP_LABELS[row.gap_type] ?? row.gap_type}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
