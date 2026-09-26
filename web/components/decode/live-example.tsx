"use client";

import { MapPin, Clock, ListChecks } from "lucide-react";
import { useDecodeExamples } from "@/components/decode/example-chips";

/** On the entry page: the first example, decoded LIVE by the real engine through `GET /decode/examples` (never a stored card). Quietly absent if the API is unreachable. */
export function LiveExample() {
  const q = useDecodeExamples();
  const ex = q.data?.examples[0];
  if (q.isError) return null;
  if (!ex)
    return <div className="shimmer mt-10 h-40 w-full max-w-xl rounded-2xl" aria-hidden />;
  const a = ex.response.card!.actions;
  const rows = [
    [MapPin, "Where", a.where?.value],
    [Clock, "When", a.when?.value],
    [ListChecks, "What", a.what?.value],
  ] as const;
  return (
    <figure className="card-soft mt-10 w-full max-w-xl p-5 text-left" data-testid="live-example">
      <figcaption className="text-sm font-medium text-muted-foreground">Someone says (decoded just now by the real engine):</figcaption>
      <blockquote className="mt-2 text-lg font-medium">“{ex.request.text}”</blockquote>
      <dl className="mt-3 space-y-2">
        {rows.map(([Icon, label, value]) =>
          value ? (
            <div key={label} className="flex items-center gap-3">
              <Icon className="size-5 shrink-0 text-primary" aria-hidden />
              <dt className="w-16 text-sm text-muted-foreground">{label}</dt>
              <dd className="text-lg font-semibold">{value}</dd>
            </div>
          ) : null,
        )}
      </dl>
      <p className="mt-3 text-sm text-muted-foreground">{ex.response.card!.phrases.map((p) => `${p.phrase} = ${p.literal}`).join(" · ")}</p>
    </figure>
  );
}
