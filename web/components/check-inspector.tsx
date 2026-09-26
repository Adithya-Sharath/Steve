"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { FactCard } from "@/components/fact-card";
import { LlmToggle, useHealth } from "@/components/llm-toggle";
import { PIPELINE, PipelineDiagram } from "@/components/pipeline-diagram";
import { CardSkeleton, ErrorState } from "@/components/states";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { AnalyzeOut } from "@/lib/types";
import { cn } from "@/lib/utils";

function useDebounced<T>(v: T, ms: number) {
  const [d, setD] = useState(v);
  useEffect(() => {
    const t = setTimeout(() => setD(v), ms);
    return () => clearTimeout(t);
  }, [v, ms]);
  return d;
}

const CAT_COLORS: Record<string, string> = {
  number: "bg-teal-soft text-primary",
  unit: "bg-understood-soft text-understood-ink",
  duration_unit: "bg-understood-soft text-understood-ink",
  frequency_phrase: "bg-understood-soft text-understood-ink",
  timing: "bg-missing-soft text-missing-ink",
  food_relation: "bg-missing-soft text-missing-ink",
  negation: "bg-negated-soft text-negated-ink",
  filler: "bg-muted text-muted-foreground",
};
const chipCls = (cat: string) => CAT_COLORS[cat] ?? (cat.startsWith("action") ? "bg-wrong-soft text-wrong-ink" : "bg-unclear-soft text-unclear-ink");

function Panel({ stage, data }: { stage: number; data: AnalyzeOut }) {
  if (stage === 0)
    return (
      <div>
        <p className="mb-3 text-sm text-muted-foreground">Each token keeps its character offsets into your original text, so evidence can be highlighted exactly.</p>
        <ul className="flex flex-wrap gap-1.5">
          {data.tokens.map((t, i) => (
            <li key={i} className="rounded-md border border-border bg-card px-2 py-1 font-mono text-xs">
              {t.text}
              {t.norm !== t.text && <span className="text-muted-foreground"> → {t.norm}</span>}
              <span className="ml-1.5 text-[10px] text-muted-foreground">{t.start}–{t.end}</span>
            </li>
          ))}
          {!data.tokens.length && <li className="text-sm text-muted-foreground">Type a reply above.</li>}
        </ul>
      </div>
    );
  if (stage === 1 || stage === 2) {
    const rows = stage === 2 ? data.matches.filter((m) => m.category === "negation" || m.category.startsWith("action") || m.negated) : data.matches;
    return (
      <div>
        <p className="mb-3 text-sm text-muted-foreground">
          {stage === 1
            ? "Every recognised word, how it matched (exact / stem / sound / fuzzy) and how sure we are. Ambiguity is kept, not hidden."
            : "Negation words and the actions they may attach to. A negated action never counts as understood."}
        </p>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr><th className="p-2.5">word</th><th className="p-2.5">means</th><th className="p-2.5">lang</th><th className="p-2.5">how</th><th className="p-2.5">score</th>{stage === 2 && <th className="p-2.5">negated?</th>}</tr>
            </thead>
            <tbody>
              {rows.map((m, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="p-2.5 font-mono">{m.text}</td>
                  <td className="p-2.5"><span className={cn("rounded-md px-1.5 py-0.5 text-xs", chipCls(m.category))}>{m.category.replace("_", " ")}</span> <span className="font-mono text-xs">{String(m.value)}</span></td>
                  <td className="p-2.5">{m.lang}</td>
                  <td className="p-2.5 text-muted-foreground">{m.kind}{m.ambiguous_with.length > 0 && " · ambiguous"}</td>
                  <td className="p-2.5 tabular-nums">{m.score}</td>
                  {stage === 2 && <td className="p-2.5">{m.negated ? "yes" : "no"}</td>}
                </tr>
              ))}
              {!rows.length && <tr><td colSpan={6} className="p-4 text-center text-muted-foreground">Nothing recognised{stage === 2 ? " as negation or action" : ""}.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  if (stage === 3)
    return (
      <div>
        <p className="mb-3 text-sm text-muted-foreground">Numbers only count next to an anchor word (a unit, counter, duration or currency). Lone numbers are listed as unclaimed and never guessed into a fact.</p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {data.slots.map((s, i) => (
            <li key={i} className="rounded-xl border border-border bg-card p-3 text-sm">
              <p className="font-medium capitalize">{s.type}{s.inferred && <span className="ml-1.5 rounded bg-missing-soft px-1.5 text-xs text-missing-ink">inferred</span>}{s.negated && <span className="ml-1.5 rounded bg-negated-soft px-1.5 text-xs text-negated-ink">negated</span>}</p>
              <p className="mt-0.5 font-mono text-xs">“{s.text}” → {String(s.value)} {s.unit ?? ""} · conf {s.confidence.toFixed(2)}</p>
            </li>
          ))}
          {!data.slots.length && <li className="text-sm text-muted-foreground">No slots filled.</li>}
        </ul>
        {data.bare_numbers.length > 0 && <p className="mt-3 text-sm text-missing-ink">Unclaimed numbers: {data.bare_numbers.join(", ")}</p>}
      </div>
    );
  return (
    <div>
      <p className="mb-3 text-sm text-muted-foreground">Exact comparison against the confirmed facts. Confidence below the threshold becomes “unclear”, never “understood”.</p>
      <ul className="grid gap-3">
        {(data.results ?? []).map((r) => (
          <FactCard key={r.fact_id} fact={{ id: r.fact_id, type: "dose", value: 0, unit: null, critical: true, label: r.fact_id.replace(/_/g, " ") }} result={r} />
        ))}
      </ul>
    </div>
  );
}

export function CheckInspector() {
  const sc = useQuery({ queryKey: ["scenarios"], queryFn: api.scenarios });
  const health = useHealth();
  const [idx, setIdx] = useState(0);
  const [stage, setStage] = useState(1);
  const [reply, setReply] = useState("randu gulika, food kazhinju, raavile vaikittu, oru week");
  const debounced = useDebounced(reply, 300);
  const scenario = sc.data?.[idx];
  const analysis = useQuery({
    queryKey: ["analyze", scenario?.id, debounced],
    queryFn: () => api.analyze(debounced, scenario!.facts, scenario!.text),
    enabled: !!scenario,
    placeholderData: (p) => p,
  });
  // give the results panel proper fact labels/types
  const decorated = useMemo(() => {
    if (!analysis.data || !scenario) return analysis.data;
    return analysis.data;
  }, [analysis.data, scenario]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">How it works</p>
      <h2 className="mt-1 max-w-3xl font-display text-5xl leading-[1.02] sm:text-6xl">Six stages. Zero LLMs in the verdict.</h2>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
        Everything below is deterministic Python you can read and test. Click a stage, then type any reply to watch it happen.
      </p>

      <div className="mt-10">
        <PipelineDiagram active={stage} onSelect={setStage} />
      </div>

      <section className="mt-12" aria-labelledby="inspector">
        <h2 id="inspector" className="font-display text-3xl">Inspector</h2>
        <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <div className="space-y-3">
            <div role="tablist" aria-label="Scenario" className="flex flex-wrap gap-2">
              {(sc.data ?? []).map((s, i) => (
                <button key={s.id} role="tab" aria-selected={i === idx} onClick={() => { setIdx(i); setReply(s.presets[1].text); }}
                  className={cn("rounded-full border px-3 py-1 text-sm", i === idx ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted")}>
                  {s.title.split(" · ")[0]}
                </button>
              ))}
            </div>
            {scenario && <p className="card-soft p-3 text-sm"><span className="text-muted-foreground">Sender:</span> {scenario.text}</p>}
            <label htmlFor="insp" className="block text-sm font-medium">Reply</label>
            <Textarea id="insp" value={reply} onChange={(e) => setReply(e.target.value)} rows={4} className="font-mono text-[15px]" spellCheck={false} />
            <div className="flex flex-wrap gap-1.5">
              {scenario?.presets.map((p) => (
                <button key={p.id} onClick={() => setReply(p.text)} className="rounded-full border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">{p.label}</button>
              ))}
            </div>
          </div>
          <div className="card-soft min-h-64 p-5">
            <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">Stage {stage + 1} · {PIPELINE[stage].title}</p>
            {sc.isError || analysis.isError ? (
              <ErrorState message="The API is not reachable." onRetry={() => { sc.refetch(); analysis.refetch(); }} />
            ) : !decorated ? (
              <CardSkeleton lines={4} />
            ) : (
              <ResultsAware stage={stage} data={decorated} facts={scenario?.facts ?? []} />
            )}
          </div>
        </div>
      </section>

      <section className="mt-16" aria-labelledby="wrapper">
        <h2 id="wrapper" className="font-display text-3xl">The wrapper test</h2>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          The operator can switch the LLM helper off for everyone (an admin-only setting). With it off, composing, replying and checking all still work end to end. The inspector above is running through the same engine either way.
        </p>
        <div className="card-soft mt-5 grid gap-6 p-6 md:grid-cols-2">
          <div className="space-y-4">
            <LlmToggle />
            <ul className="space-y-2 text-sm">
              {[
                ["Engine verdicts", "always deterministic"],
                ["Fact suggestion", health.data?.llm_enabled ? "LLM suggests, you confirm" : "built-in rules"],
                ["Speech-to-text", health.data?.stt_enabled ? "enabled (Sarvam)" : "off: typed replies"],
              ].map(([k, v]) => (
                <li key={k} className="flex items-center gap-2"><CheckCircle2 className="size-4 text-understood" aria-hidden /> <span className="text-muted-foreground">{k}:</span> <span className="font-medium">{v}</span></li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl bg-muted/60 p-4 font-mono text-xs leading-relaxed">
            <p>GET /health</p>
            <pre className="mt-2 whitespace-pre-wrap">{health.data ? JSON.stringify({ llm_enabled: health.data.llm_enabled, stt_enabled: health.data.stt_enabled, lexicon: health.data.lexicon }, null, 2) : "server offline"}</pre>
          </div>
        </div>
      </section>
    </div>
  );
}

/** Results stage needs real fact labels; the API returns fact ids, so map them back from the scenario. */
function ResultsAware({ stage, data, facts }: { stage: number; data: AnalyzeOut; facts: import("@/lib/types").Fact[] }) {
  if (stage < 4) return <Panel stage={stage} data={data} />;
  const byId = new Map(facts.map((f) => [f.id, f]));
  return (
    <div>
      <p className="mb-3 text-sm text-muted-foreground">
        {stage === 4 ? "Exact comparison against the confirmed facts." : "Final decision. Confidence below the threshold becomes “unclear”, never “understood”."}
      </p>
      <ul className="grid gap-3">
        {(data.results ?? []).map((r) => {
          const f = byId.get(r.fact_id);
          return f ? <FactCard key={r.fact_id} fact={f} result={r} /> : null;
        })}
      </ul>
    </div>
  );
}
