"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Database, RefreshCw, Trash2, Upload } from "lucide-react";
import {
  deleteKnowledgeFile,
  ingestKnowledge,
  listKnowledgeFiles,
  uploadKnowledgeFile,
} from "@/lib/api";
import type { IngestResult, KnowledgeFile } from "@/lib/types";
import { AddCuratorForm } from "./add-curator-form";
import { AppShell } from "./app-shell";
import { Sidebar } from "./sidebar";
import clsx from "clsx";

export function AdminPanel() {
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);

  const pushLog = (msg: string) => setLog((l) => [msg, ...l]);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listKnowledgeFiles();
      setFiles(data.files || []);
    } catch (err) {
      pushLog(err instanceof Error ? err.message : "Ошибка загрузки списка");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await uploadKnowledgeFile(file);
      pushLog(`Загружен: ${res.name}`);
      await loadFiles();
    } catch (err) {
      pushLog(err instanceof Error ? err.message : "Ошибка загрузки");
    }
    e.target.value = "";
  }

  async function onDelete(name: string) {
    if (!confirm(`Удалить ${name}?`)) return;
    try {
      await deleteKnowledgeFile(name);
      pushLog(`Удалён: ${name}`);
      await loadFiles();
    } catch (err) {
      pushLog(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }

  async function onIngest() {
    setIngesting(true);
    pushLog("Индексация… (1–2 мин)");
    try {
      const res: IngestResult = await ingestKnowledge();
      pushLog(
        `Готово: ${res.files} файлов → ${res.chunks} чанков, в Qdrant: ${res.total_points} точек`,
      );
    } catch (err) {
      pushLog(err instanceof Error ? err.message : "Ошибка индексации");
    } finally {
      setIngesting(false);
    }
  }

  return (
    <AppShell sidebar={<Sidebar className="hidden md:flex" />}>
      <div className="p-6 md:p-10">
        <div className="mx-auto max-w-3xl">
          <Link
            href="/"
            className="mb-6 inline-flex items-center gap-2 text-sm text-muted hover:text-accent"
          >
            <ArrowLeft className="h-4 w-4" />
            Назад к чату
          </Link>

          <h1 className="text-2xl font-bold">База знаний</h1>
          <p className="mt-1 text-muted">
            Загрузите .md / .txt и переиндексируйте Qdrant
          </p>

          <section id="curators" className="mt-8 rounded-2xl border border-border bg-surface-2 p-5">
            <h2 className="font-semibold">Кураторы</h2>
            <p className="mt-1 text-sm text-muted">
              Ученики регистрируются сами. Кураторов создаёт только модерация.
            </p>
            <AddCuratorForm
              className="mt-4"
              onSuccess={pushLog}
              onError={pushLog}
            />
          </section>

          <div className="mt-6 flex flex-wrap gap-3">
            <label
              className={clsx(
                "inline-flex cursor-pointer items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm transition hover:border-accent",
                loading && "pointer-events-none opacity-50",
              )}
            >
              <Upload className="h-4 w-4" />
              Загрузить файл
              <input type="file" accept=".md,.txt" className="hidden" onChange={onUpload} />
            </label>
            <button
              type="button"
              onClick={onIngest}
              disabled={ingesting}
              className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              <Database className="h-4 w-4" />
              {ingesting ? "Индексация…" : "Переиндексировать RAG"}
            </button>
            <button
              type="button"
              onClick={loadFiles}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm hover:border-accent"
            >
              <RefreshCw className={clsx("h-4 w-4", loading && "animate-spin")} />
              Обновить
            </button>
          </div>

          <div className="mt-6 overflow-hidden rounded-2xl border border-border">
            {files.length === 0 ? (
              <p className="p-6 text-center text-muted">Нет файлов в knowledge/</p>
            ) : (
              <ul>
                {files.map((f) => (
                  <li
                    key={f.name}
                    className="flex items-center justify-between gap-4 border-t border-border px-4 py-3 first:border-0"
                  >
                    <div>
                      <p className="font-medium">{f.name}</p>
                      <p className="text-xs text-muted">
                        {(f.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onDelete(f.name)}
                      className="rounded-lg border border-red-500/40 p-2 text-red-400 hover:bg-red-500/10"
                      aria-label={`Удалить ${f.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {log.length > 0 && (
            <div className="mt-6 rounded-xl border border-border bg-surface-2 p-4 font-mono text-xs text-muted whitespace-pre-wrap">
              {log.join("\n")}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
