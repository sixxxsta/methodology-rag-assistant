"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { CycleBanner } from "@/components/cycle-banner";
import { CuratorGuard } from "@/components/curator-guard";
import { Sidebar } from "@/components/sidebar";
import {
  fetchScoringWeights,
  updateScoringWeights,
  approveShortlist,
  discoverCompanies,
  discoverCompaniesAsync,
  enrichCompaniesBatch,
  fetchDiscoverJobStatus,
  fillShortlist,
  fetchCompaniesShortlist,
  fetchCompaniesTop,
  rejectCompany,
  verifyCompany,
} from "@/lib/api";
import { canUseEdAgent, getUser } from "@/lib/auth";
import { useActiveCycleId } from "@/lib/use-cycle";
import type { CompanyInfo } from "@/lib/types";
import clsx from "clsx";
import {
  ArrowLeft,
  Building2,
  Check,
  Loader2,
  Search,
  ThumbsDown,
  Trophy,
} from "lucide-react";

export default function CompaniesPage() {
  const [top10, setTop10] = useState<CompanyInfo[]>([]);
  const [top100, setTop100] = useState<CompanyInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<"top10" | "top100" | "shortlist">("top10");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState("");
  const [success, setSuccess] = useState("");
  const [shortlistItems, setShortlistItems] = useState<CompanyInfo[]>([]);
  const [weights, setWeights] = useState<Record<string, number> | null>(null);
  const canEdit = canUseEdAgent(getUser());
  const cycleId = useActiveCycleId();

  const load = useCallback(async () => {
    setError("");
    try {
      const [t10, t100, sl] = await Promise.all([
        fetchCompaniesTop(10),
        fetchCompaniesTop(100),
        fetchCompaniesShortlist(),
      ]);
      setTop10(t10.companies);
      setTop100(t100.companies);
      setShortlistItems(sl.companies);
      setTotal(t100.total_in_workspace);
      if (canEdit) {
        const w = await fetchScoringWeights().catch(() => null);
        if (w) setWeights(w.weights);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [canEdit]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load, cycleId]);

  const shortlist = shortlistItems;

  const rows =
    tab === "top10" ? top10 : tab === "top100" ? top100 : shortlist;

  async function onDiscoverAsync() {
    setBusy(true);
    setError("");
    setInfo("Поиск компаний запущен в фоне…");
    try {
      const { task_id } = await discoverCompaniesAsync(query.trim() || undefined, 5);
      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const job = await fetchDiscoverJobStatus(task_id);
        if (job.status === "SUCCESS" && job.result) {
          if (job.result.demo_mode && job.result.message) setInfo(job.result.message);
          else setInfo(`Готово: +${job.result.added} компаний, всего ${job.result.total}`);
          await load();
          return;
        }
        if (job.status === "FAILURE") {
          throw new Error(job.error || "Фоновая задача завершилась с ошибкой");
        }
      }
      setInfo("Задача ещё выполняется — обновите страницу позже.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка фонового поиска");
      setInfo("");
    } finally {
      setBusy(false);
    }
  }

  async function onDiscover() {
    setBusy(true);
    setError("");
    try {
      const r = await discoverCompanies(query.trim() || undefined, 3);
      if (r.demo_mode && r.message) setInfo(r.message);
      else setInfo("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка поиска");
    } finally {
      setBusy(false);
    }
  }

  async function onVerify(id: number) {
    setBusy(true);
    try {
      await verifyCompany(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onReject(id: number) {
    setBusy(true);
    try {
      await rejectCompany(id, "Не подходит");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onApproveShortlist() {
    setBusy(true);
    setSuccess("");
    try {
      const r = await approveShortlist();
      setSuccess(
        `Фаза 2 завершена (${r.shortlist_count} компаний). Откройте «Коммуникации» в меню EdAgent.`,
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGuard>
      <CuratorGuard>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar className="md:sticky md:top-0 md:h-screen" />
        <main className="flex-1 p-6 md:p-10">
          <CycleBanner />
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <Link href="/dashboard" className="flex items-center gap-2 text-sm text-muted hover:text-accent">
              <ArrowLeft className="h-4 w-4" />
              К дашборду
            </Link>
            <h1 className="text-2xl font-bold">Фаза 2 — Компании</h1>
          </div>

          <div className="mb-6 flex flex-wrap gap-4 text-sm">
            <span className="rounded-xl border border-border bg-surface-2 px-4 py-2">
              Всего в пуле: <strong>{total}</strong>
            </span>
            <span className="rounded-xl border border-accent/30 bg-accent/10 px-4 py-2">
              В шорт-листе: <strong>{shortlist.length}</strong>
            </span>
          </div>

          {canEdit && weights && (
            <section className="mb-6 rounded-2xl border border-border bg-surface-2 p-4">
              <h2 className="mb-2 text-sm font-semibold">Веса скоринга (сумма = 100)</h2>
              <div className="flex flex-wrap gap-3">
                {(["competency", "size", "education", "website", "region"] as const).map((key) => (
                  <label key={key} className="text-xs text-muted">
                    {key}
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={weights[key] ?? 0}
                      onChange={(e) =>
                        setWeights((w) => (w ? { ...w, [key]: Number(e.target.value) } : w))
                      }
                      className="mt-1 block w-16 rounded border border-border bg-surface px-2 py-1 text-sm text-text"
                    />
                  </label>
                ))}
                <button
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    if (!weights) return;
                    setBusy(true);
                    try {
                      const r = await updateScoringWeights(weights);
                      setWeights(r.weights);
                      setSuccess(`Веса обновлены, пересчитано: ${r.rescored}`);
                      await load();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Ошибка весов");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="self-end rounded-lg border border-border px-3 py-1.5 text-sm hover:border-accent"
                >
                  Применить
                </button>
              </div>
            </section>
          )}

          {canEdit && (
            <section className="mb-6 rounded-2xl border border-border bg-surface-2 p-5">
              <h2 className="mb-3 flex items-center gap-2 font-semibold">
                <Search className="h-5 w-5 text-accent" />
                Поиск работодателей (HH.ru)
              </h2>
              <div className="flex flex-wrap gap-2">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Запрос или отрасль из фазы 1"
                  className="min-w-[200px] flex-1 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm"
                />
                <button
                  type="button"
                  disabled={busy}
                  onClick={onDiscover}
                  className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Building2 className="h-4 w-4" />}
                  Найти компании
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={onDiscoverAsync}
                  className="rounded-xl border border-border px-4 py-2.5 text-sm hover:bg-surface disabled:opacity-50"
                  title="До 5 страниц HH, не блокирует интерфейс"
                >
                  В фоне (5 стр.)
                </button>
                <button
                  type="button"
                  disabled={busy || total < 1}
                  onClick={async () => {
                    setBusy(true);
                    setError("");
                    try {
                      const r = await enrichCompaniesBatch(10);
                      setInfo(`Обогащено: ${r.enriched} из ${r.attempted}`);
                      await load();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Ошибка обогащения");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="rounded-xl border border-border px-4 py-2.5 text-sm hover:bg-surface disabled:opacity-50"
                  title="Парсинг website компаний"
                >
                  Обогатить профили
                </button>
                <button
                  type="button"
                  disabled={busy || total < 1}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      setSuccess("");
                      const r = await fillShortlist(3);
                      setSuccess(
                        `В шорт-лист добавлено: ${r.companies.map((c) => c.name).join(", ")}`,
                      );
                      setTab("shortlist");
                      await load();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Ошибка");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="rounded-xl border border-border px-4 py-2.5 text-sm hover:bg-surface"
                >
                  Top-3 в шорт-лист
                </button>
                {shortlist.length > 0 && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={onApproveShortlist}
                    className="rounded-xl border border-emerald-500/50 bg-emerald-500/10 px-5 py-2.5 text-sm font-medium text-emerald-400"
                  >
                    Утвердить шорт-лист ({shortlist.length})
                  </button>
                )}
              </div>
            </section>
          )}

          {success && (
            <p className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
              {success}
            </p>
          )}

          {info && (
            <p className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200">
              {info}
            </p>
          )}

          {error && (
            <p className="mb-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-400">{error}</p>
          )}

          <div className="mb-4 flex gap-2">
            {(
              [
                ["top10", "Top-10"],
                ["top100", "Top-100"],
                ["shortlist", `Шорт-лист (${shortlist.length})`],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={clsx(
                  "rounded-lg px-4 py-2 text-sm font-medium transition",
                  tab === key ? "bg-accent/20 text-accent" : "text-muted hover:bg-surface-2",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {loading ? (
            <p className="text-muted">Загрузка…</p>
          ) : rows.length === 0 ? (
            <p className="text-muted">
              Пул пуст. {canEdit ? "Нажмите «Найти компании»." : "Ожидайте действий куратора."}
            </p>
          ) : (
            <div className="space-y-3">
              {rows.map((c, i) => (
                <article
                  key={c.id}
                  className={clsx(
                    "rounded-2xl border p-4 transition",
                    c.in_shortlist ? "border-emerald-500/40 bg-emerald-500/5" : "border-border bg-surface-2",
                  )}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        {tab === "top10" && (
                          <Trophy className="h-4 w-4 text-amber-400" />
                        )}
                        <span className="text-xs text-muted">#{i + 1}</span>
                        <h3 className="font-semibold">{c.name}</h3>
                      </div>
                      <p className="mt-1 text-sm text-muted">
                        {[c.industry, c.region, c.size_category].filter(Boolean).join(" · ")}
                      </p>
                      {c.website && (
                        <a
                          href={c.website.startsWith("http") ? c.website : `https://${c.website}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 block text-xs text-accent hover:underline"
                        >
                          {c.website}
                        </a>
                      )}
                    </div>
                    <div className="text-right">
                      <div
                        className={clsx(
                          "text-2xl font-bold",
                          (c.score ?? 0) >= 70
                            ? "text-emerald-400"
                            : (c.score ?? 0) >= 40
                              ? "text-accent"
                              : "text-muted",
                        )}
                      >
                        {c.score ?? "—"}
                      </div>
                      <p className="text-xs text-muted">скоринг</p>
                    </div>
                  </div>

                  {c.score_breakdown && (
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
                      {Object.entries(c.score_breakdown).map(([k, v]) => (
                        <span key={k} className="rounded bg-surface px-2 py-0.5">
                          {k}: {v}
                        </span>
                      ))}
                    </div>
                  )}

                  {(c.contact_name || c.contact_email) && (
                    <p className="mt-2 text-xs text-muted">
                      ЛПР: {c.contact_name}
                      {c.contact_role ? ` (${c.contact_role})` : ""}
                      {c.contact_email ? ` · ${c.contact_email}` : ""}
                    </p>
                  )}

                  {canEdit && c.status !== "rejected" && (
                    <div className="mt-3 flex gap-2">
                      {!c.in_shortlist && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => onVerify(c.id)}
                          className="flex items-center gap-1 rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs text-emerald-400"
                        >
                          <Check className="h-3 w-3" /> В шорт-лист
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => onReject(c.id)}
                        className="flex items-center gap-1 rounded-lg bg-red-500/10 px-3 py-1.5 text-xs text-red-400"
                      >
                        <ThumbsDown className="h-3 w-3" /> Отклонить
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </main>
      </div>
    </CuratorGuard>
    </AuthGuard>
  );
}
