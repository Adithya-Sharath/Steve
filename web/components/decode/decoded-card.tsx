"use client";

import { Banknote, ChevronDown, Clock, Languages, ListChecks, MapPin } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { languageInfo } from "@/lib/languages";
import { segmentText, type Highlight } from "@/lib/spans";
import type { DecodeResponse, ReplyLanguage } from "@/lib/types";
import { cn } from "@/lib/utils";

const NOT_SURE = "not_sure";

function ActionRow({ icon, label, value, dir, lang }: { icon: React.ReactNode; label: string; value: string; dir?: "ltr" | "rtl"; lang?: string }) {
  return (
    <div className="flex items-start gap-4 rounded-2xl bg-muted/60 px-4 py-3" data-testid={`action-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <span className="mt-1 grid size-10 shrink-0 place-items-center rounded-full bg-teal-soft text-primary" aria-hidden>
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold leading-snug text-foreground break-words" dir={dir} lang={lang}>{value}</p>
      </div>
    </div>
  );
}

/**
 * The decoded card, text only (D47): where / when / what / how much first, the plain-English sentence, what was heard with tappable highlights,
 * clarifying questions as big buttons (answered in place), "say it back" phrases as large text, and the translation first when a language is chosen.
 */
export function DecodedCardView({
  data,
  language,
  busy,
  onAnswer,
}: {
  data: DecodeResponse;
  language: ReplyLanguage;
  busy: boolean;
  onAnswer: (questionIndex: number, choice: string) => void;
}) {
  const card = data.card!;
  const tr = data.translation;
  const [showEnglish, setShowEnglish] = useState(false);
  const [active, setActive] = useState<string | null>(null);
  const info = languageInfo(tr?.language ?? language);
  const view = tr && !showEnglish ? tr : null; // translated card first; the toggle shows the English
  const dir = view ? info.dir : "ltr";
  const lang = view ? info.bcp47 : "en";

  const where = card.actions.where?.value;
  const when = view?.when ?? card.actions.when?.value;
  const what = view?.what ?? card.actions.what?.value;
  const how = card.actions.how_much?.value; // amount and currency are never translated
  const plain = view?.plain_english ?? card.plain_english;
  const hasActions = !!(where || when || what || how);

  const original = card.original_text;
  const highlights: Highlight[] = [
    ...card.changes.map((c, i) => ({ id: `c${i}`, span: c.span })),
    ...card.phrases.map((p, i) => ({ id: `p${i}`, span: p.span })),
    ...card.clarify.map((q, i) => ({ id: `q${i}`, span: q.span })),
    ...card.skipped.map((q, i) => ({ id: `s${i}`, span: q.span })),
  ];
  const segments = segmentText(original, highlights);

  const detail = (() => {
    if (!active) return null;
    const n = Number(active.slice(1));
    if (active[0] === "c") {
      const c = card.changes[n];
      return c ? { title: `"${c.heard}" → "${c.meant}"`, body: c.reason } : null;
    }
    if (active[0] === "p") {
      const p = card.phrases[n];
      const tp = view?.phrases[n];
      return p ? { title: p.phrase, body: `${tp?.literal ?? p.literal} ${tp?.social_meaning ?? p.social_meaning}` } : null;
    }
    const q = (active[0] === "q" ? card.clarify : card.skipped)[n];
    return q ? { title: `"${q.span.text}"`, body: q.question } : null;
  })();

  return (
    <article aria-label="Decoded message" className="card-soft space-y-5 p-4 sm:p-6" data-testid="decoded-card">
      {data.notes.length > 0 && (
        <ul className="space-y-1 rounded-xl bg-missing-soft px-4 py-3 text-sm text-missing-ink" role="status">
          {data.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}

      {tr && (
        <div className="flex justify-end">
          <Button variant="outline" className="h-14 px-5 text-base" onClick={() => setShowEnglish((v) => !v)} aria-pressed={showEnglish}>
            <Languages aria-hidden /> {showEnglish ? `Show ${info.native}` : "Show English"}
          </Button>
        </div>
      )}

      {hasActions && (
        <div className="space-y-2" data-testid="actions">
          {where && <ActionRow icon={<MapPin className="size-5" />} label="Where" value={where} lang="en" />}
          {when && <ActionRow icon={<Clock className="size-5" />} label="When" value={when} dir={dir} lang={lang} />}
          {what && <ActionRow icon={<ListChecks className="size-5" />} label="What" value={what} dir={dir} lang={lang} />}
          {how && <ActionRow icon={<Banknote className="size-5" />} label="How much" value={how} lang="en" />}
        </div>
      )}

      <p className="text-xl leading-relaxed text-foreground" dir={dir} lang={lang} data-testid="plain-english">
        {plain}
      </p>

      {(card.phrases.length > 0 || view?.phrases.length) && !detail && (
        <p className="text-sm text-muted-foreground">Tap a highlighted word below to see what it means.</p>
      )}

      <section aria-label="What they said" className="rounded-2xl border border-border p-4">
        <h2 className="text-sm font-medium text-muted-foreground">{data.transcript ? "I heard" : "They said"}</h2>
        <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-2 text-lg leading-relaxed" lang="en" data-testid="original">
          {segments.map((s, i) =>
            s.ids.length === 0 ? (
              <span key={i}>{s.text}</span>
            ) : (
              <button
                key={i}
                type="button"
                onClick={() => setActive(active === s.ids[0] ? null : s.ids[0])}
                aria-pressed={active === s.ids[0]}
                className={cn(
                  "inline-flex min-h-14 items-center rounded-xl px-3 underline decoration-2 underline-offset-4",
                  s.ids[0][0] === "p" ? "bg-teal-soft decoration-primary" : s.ids[0][0] === "c" ? "bg-missing-soft decoration-missing" : "bg-unclear-soft decoration-unclear",
                )}
              >
                {s.text}
              </button>
            ),
          )}
        </p>
        {detail && (
          <div role="status" className="mt-3 rounded-xl bg-muted px-4 py-3" data-testid="highlight-detail" dir={dir} lang={lang}>
            <p className="font-medium">{detail.title}</p>
            <p className="mt-1 text-muted-foreground">{detail.body}</p>
          </div>
        )}
      </section>

      {card.clarify.length > 0 && data.decode_id && (
        <section aria-label="Questions" className="space-y-4" data-testid="questions">
          {card.clarify.map((q, qi) => (
            <div key={`${q.span.start}-${q.question}`} className="rounded-2xl border-2 border-unclear bg-unclear-soft p-4">
              <p className="text-xl font-semibold" dir={dir} lang={lang}>{view?.questions[qi] ?? q.question}</p>
              <div className="mt-3 flex flex-wrap gap-3">
                {q.options.map((o) => (
                  <Button key={o} variant="outline" className="h-14 min-w-28 px-6 text-lg" disabled={busy} onClick={() => onAnswer(qi, o)}>
                    {o}
                  </Button>
                ))}
                <Button variant="ghost" className="h-14 px-6 text-lg" disabled={busy} onClick={() => onAnswer(qi, NOT_SURE)}>
                  Not sure
                </Button>
              </div>
            </div>
          ))}
        </section>
      )}

      {card.tips.length > 0 && (
        <details className="group rounded-2xl border border-border px-4 py-3">
          <summary className="flex min-h-10 cursor-pointer list-none items-center justify-between gap-2 text-sm font-medium">
            Why this sounded different <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <p className="mt-2 text-muted-foreground" dir={dir} lang={lang}>{view?.tip ?? card.tips[0]}</p>
        </details>
      )}

      {data.say_back.length > 0 && (
        <section aria-label="Say it back" className="rounded-2xl bg-primary px-4 py-5 text-primary-foreground" data-testid="say-back">
          <h2 className="text-sm font-medium opacity-90">Say it back: show this to them</h2>
          <ul className="mt-2 space-y-2">
            {data.say_back.map((s) => (
              <li key={s} className="font-display text-3xl leading-tight" lang="en">{s}</li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
