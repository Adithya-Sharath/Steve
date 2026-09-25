"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, LayoutGroup } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { FactCard } from "@/components/fact-card";
import { CardSkeleton, ErrorState } from "@/components/states";
import { Transcript } from "@/components/transcript";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { LANG_LABEL } from "@/lib/status";
import type { Highlight } from "@/lib/spans";
import type { FactResult } from "@/lib/types";
import { cn } from "@/lib/utils";

function useDebounced<T>(v: T, ms: number) {
  const [d, setD] = useState(v);
  useEffect(() => {
    const t = setTimeout(() => setD(v), ms);
    return () => clearTimeout(t);
  }, [v, ms]);
  return d;
}

/** Live playground: pick a scenario, type any reply, results come from POST /check (the real engine). */
export function Playground({ initialScenario = 0, className }: { initialScenario?: number; className?: string }) {
  const sc = useQuery({ queryKey: ["scenarios"], queryFn: api.scenarios });
  const [idx, setIdx] = useState(initialScenario);
  const scenario = sc.data?.[idx];
  const [reply, setReply] = useState("randu gulika, food kazhinju, raavile vaikittu, oru week");
  const [active, setActive] = useState<string | null>(null);
  const debounced = useDebounced(reply, 350);

  const check = useQuery({
    queryKey: ["check", scenario?.id, debounced],
    queryFn: () => api.check(scenario!.facts, debounced, scenario!.text),
    enabled: !!scenario,
    placeholderData: (prev) => prev,
  });

  const results = useMemo(() => new Map((check.data ?? []).map((r: FactResult) => [r.fact_id, r])), [check.data]);
  const highlights: Highlight[] = useMemo(
    () => (check.data ?? []).flatMap((r) => r.evidence.map((span, i) => ({ id: r.fact_id, span, status: r.status, key: i }))),
    [check.data],
  );

  if (sc.isError) return <ErrorState message="The demo server isn't running, so the live playground can't check replies." onRetry={() => sc.refetch()} />;
  if (!scenario) return <CardSkeleton lines={5} />;

  return (
    <div className={cn("grid gap-6 lg:grid-cols-[1.05fr_1fr]", className)}>
      <div className="space-y-4">
        <div role="tablist" aria-label="Scenario" className="flex flex-wrap gap-2">
          {sc.data!.map((s, i) => (
            <button
              key={s.id}
              role="tab"
              aria-selected={i === idx}
              onClick={() => {
                setIdx(i);
                setReply(s.presets[1].text);
              }}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm transition-colors",
                i === idx ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted",
              )}
            >
              {s.title.split(" · ")[0]}
            </button>
          ))}
        </div>
        <div className="card-soft p-4">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Sender wrote</p>
          <p className="mt-1.5 leading-relaxed">{scenario.text}</p>
        </div>
        <div>
          <label htmlFor="pg-reply" className="mb-1.5 block text-sm font-medium">
            Reader&apos;s reply — any language mix, any spelling
          </label>
          <Textarea id="pg-reply" value={reply} onChange={(e) => setReply(e.target.value)} rows={3} className="font-mono text-[15px]" spellCheck={false} />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {scenario.presets.map((p) => (
              <button
                key={p.id}
                onClick={() => setReply(p.text)}
                className="rounded-full border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {p.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Presets: {scenario.presets.map((p) => LANG_LABEL[p.lang_mix] ?? p.lang_mix).join(" · ")}
          </p>
        </div>
        {check.data && highlights.length > 0 && (
          <div className="card-soft p-4">
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">Verbatim, evidence highlighted</p>
            <Transcript text={debounced} highlights={highlights} activeId={active} onHover={setActive} />
          </div>
        )}
      </div>
      <div>
        {check.isError ? (
          <ErrorState message="Could not check that reply." onRetry={() => check.refetch()} />
        ) : (
          <LayoutGroup>
            <ul className="grid gap-3" aria-live="polite">
              <AnimatePresence mode="popLayout">
                {scenario.facts.map((f) => (
                  <FactCard key={`${scenario.id}-${f.id}`} fact={f} result={results.get(f.id)} pending={!results.get(f.id)} active={active === f.id} onHover={setActive} />
                ))}
              </AnimatePresence>
            </ul>
          </LayoutGroup>
        )}
      </div>
    </div>
  );
}
