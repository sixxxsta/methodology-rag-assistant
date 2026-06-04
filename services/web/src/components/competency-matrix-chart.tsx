"use client";

const GAP_LABELS: Record<string, string> = {
  missing_in_program: "Нет в программе",
  undertrained: "Недостаточно",
  overtrained: "Избыток",
  niche_program: "Ниша программы",
  aligned: "Соответствует",
};

const GAP_COLORS: Record<string, string> = {
  missing_in_program: "bg-amber-500",
  undertrained: "bg-orange-500",
  overtrained: "bg-sky-500",
  niche_program: "bg-violet-500",
  aligned: "bg-emerald-500",
};

type ChartData = {
  summary: { total: number; gaps: number; aligned: number; excess: number };
  by_gap_type: Array<{ gap_type: string; count: number }>;
  comparison: Array<{
    name: string;
    program_level: number;
    industry_level_est: number;
    industry_demand_pct: number;
    gap_type: string;
  }>;
};

export function CompetencyMatrixChart({ data }: { data: ChartData }) {
  const maxCount = Math.max(...data.by_gap_type.map((g) => g.count), 1);
  const maxLevel = 5;

  return (
    <section className="mb-8 grid gap-6 lg:grid-cols-2">
      <div className="rounded-2xl border border-border bg-surface-2 p-5">
        <h2 className="mb-4 font-semibold">Распределение по типам пробелов</h2>
        <ul className="space-y-3">
          {data.by_gap_type.map((row) => (
            <li key={row.gap_type}>
              <div className="mb-1 flex justify-between text-sm">
                <span>{GAP_LABELS[row.gap_type] ?? row.gap_type}</span>
                <span className="text-muted">{row.count}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface">
                <div
                  className={`h-full rounded-full ${GAP_COLORS[row.gap_type] ?? "bg-accent"}`}
                  style={{ width: `${(row.count / maxCount) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-muted">
          Всего навыков: {data.summary.total} · пробелы: {data.summary.gaps} ·
          соответствие: {data.summary.aligned}
        </p>
      </div>

      <div className="rounded-2xl border border-border bg-surface-2 p-5">
        <h2 className="mb-4 font-semibold">Программа vs индустрия (топ-15)</h2>
        <ul className="max-h-80 space-y-3 overflow-y-auto pr-1">
          {data.comparison.map((row) => (
            <li key={row.name}>
              <div className="mb-1 flex justify-between gap-2 text-sm">
                <span className="truncate">{row.name}</span>
                <span className="shrink-0 text-xs text-muted">
                  {GAP_LABELS[row.gap_type] ?? row.gap_type}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-muted">Программа</span>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface">
                    <div
                      className="h-full rounded-full bg-accent/70"
                      style={{ width: `${(row.program_level / maxLevel) * 100}%` }}
                    />
                  </div>
                </div>
                <div>
                  <span className="text-muted">Индустрия</span>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface">
                    <div
                      className="h-full rounded-full bg-emerald-500/80"
                      style={{ width: `${(row.industry_level_est / maxLevel) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
        {data.comparison.length === 0 && (
          <p className="text-sm text-muted">Соберите вакансии для построения графика.</p>
        )}
      </div>
    </section>
  );
}
