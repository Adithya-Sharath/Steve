"use client";

import { LANGUAGES } from "@/lib/languages";
import type { ReplyLanguage } from "@/lib/types";
import { cn } from "@/lib/utils";

/** First-run picker (and the header's "change language"): each language in its own script, big touch targets. Stored on this phone only. */
export function LanguagePicker({ current, onPick }: { current?: ReplyLanguage | null; onPick: (l: ReplyLanguage) => void }) {
  return (
    <section aria-labelledby="pick-lang" className="mx-auto w-full max-w-md px-4 py-8">
      <h1 id="pick-lang" className="font-display text-4xl leading-tight">Choose your language</h1>
      <p className="mt-2 text-muted-foreground">Steve shows what it heard in this language, next to the English. You can change it any time.</p>
      <ul className="mt-6 grid grid-cols-2 gap-3">
        {LANGUAGES.map((l) => (
          <li key={l.id}>
            <button
              type="button"
              lang={l.bcp47}
              dir={l.dir}
              aria-label={`${l.native} (${l.english})`}
              aria-pressed={current === l.id}
              onClick={() => onPick(l.id)}
              className={cn(
                "flex min-h-16 w-full items-center justify-center rounded-2xl border-2 px-3 py-3 text-xl font-medium transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                current === l.id ? "border-primary bg-teal-soft text-foreground" : "border-border bg-card hover:bg-muted",
              )}
            >
              {l.native}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
