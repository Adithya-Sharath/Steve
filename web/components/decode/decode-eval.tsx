"use client";

import { useQuery } from "@tanstack/react-query";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/states";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { withWake } from "@/lib/waking";

/** The Decode numbers, from `GET /decode/eval` (a committed results file, never computed here). Every section shows the label that must travel with its numbers. */
export function DecodeEval() {
  const q = useQuery({ queryKey: ["decode-eval"], queryFn: () => withWake(api.decodeEval), retry: false });
  if (q.isLoading) return <CardSkeleton lines={6} />;
  if (q.isError) return <ErrorState message={(q.error as Error).message} onRetry={() => q.refetch()} />;
  const d = q.data!;
  if (!d.available) return <EmptyState title="No Decode results yet" body={d.message ?? "Run python eval/decode_metrics_export.py."} />;
  return (
    <div className="space-y-6">
      <div role="note" className="rounded-2xl border-2 border-missing bg-missing-soft px-4 py-3 text-missing-ink">
        <p className="font-medium">Read this first</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
          {d.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </div>
      {d.sections.map((s) => (
        <section key={s.id} className={cn("card-soft p-4 sm:p-5", s.id === "missing" && "border-2 border-missing")} aria-labelledby={`ev-${s.id}`} data-testid={`eval-${s.id}`}>
          <h2 id={`ev-${s.id}`} className="text-xl font-semibold">{s.title}</h2>
          <p className="mt-2 inline-block rounded-full bg-unclear-soft px-3 py-1 text-xs font-medium text-unclear-ink" data-testid="eval-label">{s.label}</p>
          {s.note && <p className="mt-2 text-sm text-muted-foreground">{s.note}</p>}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">{s.title}</caption>
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th scope="col" className="py-2 pr-3 font-medium">Measure</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Result</th>
                  <th scope="col" className="hidden py-2 font-medium sm:table-cell">Detail</th>
                </tr>
              </thead>
              <tbody>
                {s.rows.map((r) => (
                  <tr key={r.metric} className="border-b border-border/60 align-top">
                    <td className="py-2 pr-3">{r.metric}</td>
                    <td className="py-2 pr-3 font-mono font-medium">{r.value}</td>
                    <td className="hidden py-2 text-muted-foreground sm:table-cell">{r.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
