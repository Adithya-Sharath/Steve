"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DecodeExample } from "@/lib/types";
import { withWake } from "@/lib/waking";

export function useDecodeExamples() {
  return useQuery({ queryKey: ["decode-examples"], queryFn: () => withWake(api.decodeExamples), retry: false, staleTime: 5 * 60_000 });
}

/** One-tap examples from `GET /decode/examples`. The chips only carry the INPUT; the card you get is decoded live through the real API, never a stored answer. */
export function ExampleChips({ onPick, disabled }: { onPick: (ex: DecodeExample) => void; disabled: boolean }) {
  const q = useDecodeExamples();
  if (q.isError) return null; // the examples are a convenience: the rest of the screen works without them
  return (
    <section aria-label="Examples" data-testid="examples">
      <h2 className="text-sm font-medium text-muted-foreground">Try an example</h2>
      {q.isLoading ? (
        <div className="mt-2 flex flex-wrap gap-2" aria-hidden>
          {[120, 160, 140].map((w) => (
            <span key={w} className="shimmer h-11 rounded-full" style={{ width: w }} />
          ))}
        </div>
      ) : (
        <ul className="mt-2 flex flex-wrap gap-2">
          {q.data?.examples.map((ex) => (
            <li key={ex.id}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onPick(ex)}
                className="min-h-11 rounded-full border border-border bg-card px-4 py-2 text-left text-sm font-medium hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50"
              >
                {ex.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
