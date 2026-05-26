"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";
import { fetchProjectCatalog } from "@/lib/api";
import { ArrowLeft, BookOpen } from "lucide-react";

export default function CatalogPage() {
  const [items, setItems] = useState<
    Awaited<ReturnType<typeof fetchProjectCatalog>>["items"]
  >([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await fetchProjectCatalog();
      setItems(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar className="md:sticky md:top-0 md:h-screen" />
        <main className="flex-1 p-6 md:p-10">
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard/projects"
              className="flex items-center gap-2 text-sm text-muted hover:text-accent"
            >
              <ArrowLeft className="h-4 w-4" />
              К проектам
            </Link>
            <h1 className="flex items-center gap-2 text-2xl font-bold">
              <BookOpen className="h-7 w-7 text-accent" />
              Каталог проектов
            </h1>
          </div>

          <p className="mb-6 text-sm text-muted">
            Опубликованные проекты для студенческих команд программы ПроКомпетенции.
          </p>

          {loading && <p className="text-muted">Загрузка…</p>}
          {error && <p className="text-sm text-red-400">{error}</p>}

          {!loading && items.length === 0 && (
            <p className="rounded-lg border border-border bg-surface-2 px-4 py-6 text-sm text-muted">
              Каталог пока пуст. Администратор публикует проекты после согласования с партнёром.
            </p>
          )}

          <ul className="grid gap-4 sm:grid-cols-2">
            {items.map((item) => (
              <li
                key={item.id}
                className="rounded-2xl border border-border bg-surface-2 p-5 transition hover:border-accent/40"
              >
                <h2 className="font-semibold leading-snug">{item.title}</h2>
                {item.company_name && (
                  <p className="mt-1 text-sm text-accent">{item.company_name}</p>
                )}
                {item.description && (
                  <p className="mt-2 text-sm text-muted line-clamp-4">{item.description}</p>
                )}
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
                  {item.team_size != null && <span>Команда: {item.team_size}</span>}
                  {item.duration_weeks != null && (
                    <span>Срок: {item.duration_weeks} нед.</span>
                  )}
                </div>
                {item.competencies && (
                  <p className="mt-2 text-xs text-muted">
                    Компетенции: {item.competencies}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </main>
      </div>
    </AuthGuard>
  );
}
