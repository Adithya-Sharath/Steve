"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, ListChecks, Loader2, MapPin } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { withWake } from "@/lib/waking";

/**
 * On the entry page: nothing is decoded until the visitor asks. The button fetches `GET /decode/examples` and the FIRST example is then decoded by the real engine
 * at that moment (never a stored card). Quietly falls back to a message if the API is unreachable.
 */
export function LiveExample() {
  const [asked, setAsked] = useState(false);
  const q = useQuery({ queryKey: ["intro-example"], queryFn: () => withWake(api.decodeExamples), enabled: asked, retry: false });
  const ex = q.data?.examples[0];
  if (!asked)
    return (
      <div className="mt-10 w-full max-w-xl">
        <Button variant="outline" className="h-12 px-6 text-base" onClick={() => setAsked(true)} data-testid="see-example">
          See an example decode
        </Button>
      </div>
    );
  if (q.isError) return <p className="mt-10 text-sm text-muted-foreground" role="status">The example could not be loaded right now. Tap “Try it” to use the real thing.</p>;
  if (!ex)
    return (
      <p role="status" className="mt-10 flex items-center gap-2 text-muted-foreground" data-testid="example-loading">
        <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden /> decoding…
      </p>
    );
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
