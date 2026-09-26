"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical, Terminal } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricTile } from "@/components/metric-tile";
import { StatusBadge } from "@/components/status-badge";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/states";
import { api } from "@/lib/api";
import { LANG_LABEL, STATUS_META, STATUS_ORDER } from "@/lib/status";
import type { EvalBucket, EvalCase, EvalResults, Status } from "@/lib/types";
import { cn } from "@/lib/utils";

const pct = (x: number | undefined | null) => (x == null ? null : Math.round(x * 1000) / 10);
const STATUSES: Status[] = ["understood", "wrong", "missing", "negated", "unclear"];

function BucketChart({ title, metric, ours, base }: { title: string; metric: "accuracy" | "false_understood_rate"; ours: Record<string, EvalBucket>; base?: Record<string, EvalBucket> }) {
  const keys = Object.keys(ours);
  const data = keys.map((k) => ({
    name: LANG_LABEL[k] ?? k,
    Ours: pct(ours[k][metric]),
    Baseline: base?.[k] ? pct(base[k][metric]) : null,
    n: ours[k].n,
  }));
  const hasBase = data.some((d) => d.Baseline != null);
  return (
    <div className="card-soft p-5">
      <h2 className="font-medium">{title}</h2>
      <div className="mt-4 h-64" role="img" aria-label={`${title}: ${data.map((d) => `${d.name} ${d.Ours}%`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
            <YAxis unit="%" tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} domain={[0, 100]} />
            <Tooltip cursor={{ fill: "var(--muted)" }} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 12, color: "var(--foreground)" }} formatter={(v) => (v == null ? "n/a" : `${v}%`)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="Ours" fill="var(--primary)" radius={[6, 6, 0, 0]} isAnimationActive />
            {hasBase && <Bar dataKey="Baseline" fill="var(--muted-foreground)" radius={[6, 6, 0, 0]} />}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Confusion({ matrix, label }: { matrix: Record<string, Record<string, number>>; label: string }) {
  const max = Math.max(1, ...STATUSES.flatMap((g) => STATUSES.map((p) => matrix[g]?.[p] ?? 0)));
  return (
    <div className="card-soft overflow-x-auto p-5">
      <h2 className="font-medium">Confusion matrix · {label}</h2>
      <p className="text-xs text-muted-foreground">Rows: what a human says is right (gold). Columns: what the system said.</p>
      <table className="mt-4 w-full min-w-[480px] border-separate border-spacing-1 text-center text-sm">
        <thead>
          <tr>
            <th className="w-24 text-left text-xs font-normal text-muted-foreground">gold ↓ / said →</th>
            {STATUSES.map((p) => <th key={p} className="p-1"><StatusBadge status={p} size="sm" animate={false} /></th>)}
          </tr>
        </thead>
        <tbody>
          {STATUSES.map((g) => (
            <tr key={g}>
              <th scope="row" className="text-left"><StatusBadge status={g} size="sm" animate={false} /></th>
              {STATUSES.map((p) => {
                const n = matrix[g]?.[p] ?? 0;
                const bad = p === "understood" && g !== "understood";
                const good = g === p;
                return (
                  <td
                    key={p}
                    className={cn("rounded-lg py-2.5 tabular-nums", n === 0 && "text-muted-foreground/50", bad && n > 0 && "font-semibold ring-2 ring-wrong")}
                    style={{ background: n === 0 ? "var(--muted)" : `color-mix(in oklch, ${good ? "var(--understood)" : bad ? "var(--wrong)" : "var(--missing)"} ${Math.max(14, (n / max) * 70)}%, var(--card))` }}
                    title={bad ? "false 'understood' (the worst error)" : undefined}
                  >
                    {n}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-muted-foreground">Red-ringed cells are false “understood”: the worst possible error.</p>
    </div>
  );
}

function Explorer({ cases, hasBaseline }: { cases: EvalCase[]; hasBaseline: boolean }) {
  const [who, setWho] = useState<"either" | "engine" | "baseline">("either");
  const [src, setSrc] = useState<"all" | "synthetic" | "handwritten">("all");
  const [lang, setLang] = useState("all");
  const langs = useMemo(() => [...new Set(cases.map((c) => c.lang_mix))], [cases]);
  const rows = useMemo(
    () =>
      cases.filter((c) => {
        const eWrong = c.engine.status !== c.gold;
        const bWrong = c.baseline?.status != null && c.baseline.status !== c.gold;
        if (who === "engine" && !eWrong) return false;
        if (who === "baseline" && !bWrong) return false;
        if (who === "either" && !(eWrong || bWrong)) return false;
        if (src === "synthetic" && !c.synthetic) return false;
        if (src === "handwritten" && c.synthetic) return false;
        if (lang !== "all" && c.lang_mix !== lang) return false;
        return true;
      }),
    [cases, who, src, lang],
  );
  const sel = "h-8 rounded-lg border border-input bg-background px-2 text-sm";
  return (
    <div className="card-soft p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-medium">Error explorer <span className="text-sm font-normal text-muted-foreground">({rows.length} cases)</span></h2>
        <div className="flex flex-wrap gap-2">
          <select className={sel} value={who} onChange={(e) => setWho(e.target.value as typeof who)} aria-label="Who was wrong">
            <option value="either">Either system wrong</option><option value="engine">Our engine wrong</option>{hasBaseline && <option value="baseline">Baseline wrong</option>}
          </select>
          <select className={sel} value={src} onChange={(e) => setSrc(e.target.value as typeof src)} aria-label="Data source">
            <option value="all">All data</option><option value="handwritten">Hand-written</option><option value="synthetic">Synthetic</option>
          </select>
          <select className={sel} value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
            <option value="all">All languages</option>{langs.map((l) => <option key={l} value={l}>{LANG_LABEL[l] ?? l}</option>)}
          </select>
        </div>
      </div>
      <div className="mt-4 max-h-[32rem] overflow-auto rounded-xl border border-border">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="sticky top-0 bg-muted text-xs uppercase tracking-wide text-muted-foreground">
            <tr><th className="p-2.5">Reply</th><th className="p-2.5">Fact</th><th className="p-2.5">Gold</th><th className="p-2.5">Ours</th>{hasBaseline && <th className="p-2.5">Baseline</th>}</tr>
          </thead>
          <tbody>
            {rows.slice(0, 200).map((c, i) => (
              <tr key={`${c.reply_id}-${c.fact_id}-${i}`} className="border-t border-border align-top">
                <td className="max-w-xs p-2.5"><p className="font-mono text-xs">{c.reply_text}</p><p className="mt-1 text-[11px] text-muted-foreground">{LANG_LABEL[c.lang_mix] ?? c.lang_mix} · {c.synthetic ? "synthetic" : "hand-written"}</p></td>
                <td className="p-2.5">{c.fact_label}<p className="text-[11px] text-muted-foreground">{c.fact_type}</p></td>
                <td className="p-2.5"><StatusBadge status={c.gold} size="sm" animate={false} /></td>
                <td className="p-2.5"><StatusBadge status={c.engine.status} size="sm" animate={false} /><p className={cn("mt-1 max-w-56 text-[11px] leading-snug", c.engine.status === c.gold ? "text-muted-foreground" : "text-wrong-ink")}>{c.engine.reason}</p></td>
                {hasBaseline && <td className="p-2.5">{c.baseline?.status ? <StatusBadge status={c.baseline.status} size="sm" animate={false} /> : <span className="text-muted-foreground">n/a</span>}</td>}
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={5} className="p-6 text-center text-muted-foreground">No errors match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Body({ r }: { r: EvalResults }) {
  const [metric, setMetric] = useState<"accuracy" | "false_understood_rate">("accuracy");
  const eng = r.engine!;
  const base = r.baseline?.available ? r.baseline : undefined;
  const o = eng.overall!;
  const bo = base?.overall;
  const [confSys, setConfSys] = useState<"engine" | "baseline">("engine");
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-3">
        <MetricTile label="Fact-level accuracy · ours" value={pct(o.accuracy)} decimals={1} suffix="%" sub={`${o.correct} of ${o.n} fact checks. ${bo ? `Baseline: ${pct(bo.accuracy)}%.` : "Baseline not run (no Gemini key)."}`} />
        <MetricTile
          label="False “understood” rate · ours"
          value={pct(o.false_understood_rate)}
          decimals={1}
          suffix="%"
          tone={o.false_understood === 0 ? "good" : "bad"}
          emphasis
          sub={`${o.false_understood} of ${o.false_understood_denominator} facts that were NOT understood were called “understood”. ${bo ? `Baseline: ${pct(bo.false_understood_rate)}%.` : "Baseline not run."}`}
        />
        <MetricTile
          label="Consistency across runs"
          value={pct(base?.consistency?.mean_agreement ?? 1)}
          decimals={1}
          suffix="%"
          sub={base?.consistency ? `Baseline agreed with itself on ${pct(base.consistency.mean_agreement)}% of items across ${base.consistency.runs} runs. Our engine is deterministic: 100% by construction.` : "Our engine is deterministic: 100% by construction. Baseline consistency needs a Gemini key to measure."}
        />
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Chart metric:</span>
        {(["accuracy", "false_understood_rate"] as const).map((m) => (
          <button key={m} onClick={() => setMetric(m)} aria-pressed={metric === m} className={cn("rounded-full border px-3 py-1", metric === m ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card")}>
            {m === "accuracy" ? "Accuracy" : "False “understood” rate"}
          </button>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <BucketChart title="By language mix" metric={metric} ours={eng.by_language} base={base?.by_language} />
        <BucketChart title="By fact type" metric={metric} ours={eng.by_type} base={base?.by_type} />
      </div>

      {Object.keys(eng.by_source).length > 0 && (
        <div className="card-soft p-5">
          <h2 className="font-medium">Synthetic vs hand-written</h2>
          <p className="text-sm text-muted-foreground">Synthetic variants reuse vocabulary the lexicon already knows, so they flatter the engine. Trust the hand-written row more, and add your own replies.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {Object.entries(eng.by_source).map(([k, b]) => (
              <div key={k} className="rounded-xl border border-border p-3 text-sm">
                <p className="font-medium capitalize">{k}</p>
                <p className="text-muted-foreground">{b.n} checks · accuracy {pct(b.accuracy)}% · false “understood” {b.false_understood} / {b.false_understood_denominator}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        {base && (
          <div className="mb-3 flex gap-2 text-sm">
            {(["engine", "baseline"] as const).map((s) => <button key={s} onClick={() => setConfSys(s)} aria-pressed={confSys === s} className={cn("rounded-full border px-3 py-1 capitalize", confSys === s ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card")}>{s === "engine" ? "Ours" : "Baseline"}</button>)}
          </div>
        )}
        <Confusion matrix={confSys === "engine" ? eng.confusion : base!.confusion} label={confSys === "engine" ? "ours" : "baseline"} />
      </div>

      <Explorer cases={r.cases ?? []} hasBaseline={!!base} />

      {r.caveats && (
        <div className="rounded-2xl border border-missing/40 bg-missing-soft p-5 text-sm text-missing-ink">
          <p className="font-medium">Read this before trusting any number</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">{r.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

export function CheckEval() {
  const q = useQuery({ queryKey: ["eval"], queryFn: api.evalResults });
  const r = q.data;
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">Evaluation</p>
      <h2 className="mt-1 max-w-3xl font-display text-5xl leading-[1.02] sm:text-6xl">The number that matters: false “understood”.</h2>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
        A wrong fact marked understood is the worst error a teach-back tool can make. We report it first, and we report where we lose.
        {r?.available && r.n_fact_checks ? ` ${r.n_fact_checks} labelled fact checks across ${r.n_replies} replies.` : ""}
      </p>
      <div className="mt-10">
        {q.isLoading ? (
          <div className="grid gap-4 md:grid-cols-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
        ) : q.isError ? (
          <ErrorState message={(q.error as Error).message} onRetry={() => q.refetch()} />
        ) : !r?.available || !r.engine?.overall ? (
          <EmptyState
            icon={<FlaskConical className="size-8" />}
            title="No results yet"
            body="Numbers here are never hard-coded. Generate them by running the evaluation pipeline."
            action={<code className="inline-flex items-center gap-2 rounded-xl bg-muted px-4 py-2 font-mono text-sm"><Terminal className="size-4" /> make eval</code>}
          />
        ) : (
          <Body r={r} />
        )}
      </div>
    </div>
  );
}

void STATUS_ORDER;
void STATUS_META;
