"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useDecodeExamples } from "@/components/decode/example-chips";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { ACCENTS } from "@/lib/languages";
import type { AccentHint, InspectResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { withWake } from "@/lib/waking";

const DECISION: Record<string, { label: string; cls: string; why: (m: number) => string }> = {
  fits: { label: "fits", cls: "bg-understood-soft text-understood-ink", why: () => "The word is already the kind of word this spot expects, so it is left alone." },
  no_alternative: { label: "no alternative", cls: "bg-muted text-muted-foreground", why: () => "No sound-alike of the right kind is close enough, so the word is kept." },
  keep: { label: "kept", cls: "bg-muted text-muted-foreground", why: (m) => `The best alternative beats the word by only ${m.toFixed(2)}: not enough to change or even ask, so the word is kept.` },
  rewrite: { label: "rewritten", cls: "bg-teal-soft text-primary", why: (m) => `One alternative wins by ${m.toFixed(2)} (a clear win is 1.6 or more, and nothing else is close), so the word is read as meant.` },
  clarify: { label: "asks a question", cls: "bg-unclear-soft text-unclear-ink", why: (m) => `The best alternative wins by ${m.toFixed(2)} (0.6 to 1.6) or another is close: too uncertain to decide silently, so Steve asks.` },
};

const STAGES = ["Tokens", "Local phrases", "Critical spots", "Candidates and the decision", "Words as meant", "Where / when / what / how much"];

function Stage({ n, title, blurb, children }: { n: number; title: string; blurb: string; children: React.ReactNode }) {
  return (
    <section className="card-soft p-4 sm:p-5" aria-labelledby={`stage-${n}`}>
      <h3 id={`stage-${n}`} className="flex items-center gap-3 text-lg font-semibold">
        <span className="grid size-8 place-items-center rounded-full bg-primary text-sm text-primary-foreground" aria-hidden>{n}</span>
        {title}
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">{blurb}</p>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Chip({ children, className }: { children: React.ReactNode; className?: string }) {
  return <li className={cn("rounded-lg border border-border bg-card px-2.5 py-1.5 font-mono text-sm", className)}>{children}</li>;
}

function Stages({ d }: { d: InspectResult }) {
  const a = d.card.actions;
  const rows = [["Where", a.where?.value], ["When", a.when?.value], ["What", a.what?.value], ["How much", a.how_much?.value]] as const;
  return (
    <div className="space-y-4" data-testid="inspector-stages">
      <Stage n={1} title={STAGES[0]} blurb="The text is split into words, each keeping its character offsets so evidence can be pointed at exactly.">
        <ul className="flex flex-wrap gap-1.5">
          {d.tokens.map((t) => (
            <Chip key={t.i}>{t.text}<span className="ml-1.5 text-[10px] text-muted-foreground">{t.start}–{t.end}</span></Chip>
          ))}
        </ul>
      </Stage>
      <Stage n={2} title={STAGES[1]} blurb="Local phrases (yalla, khalas, Maghrib ...) are found first and explained, never judged. They are not treated as misspellings.">
        {d.glossary.length ? (
          <ul className="flex flex-wrap gap-1.5">
            {d.glossary.map((g) => (
              <Chip key={g.phrase} className="bg-teal-soft text-primary">{g.phrase}<span className="ml-1.5 text-[10px]">{g.category}</span></Chip>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No local phrase found in this text.</p>
        )}
      </Stage>
      <Stage n={3} title={STAGES[2]} blurb="Only words in a spot where a place, time, number, amount or thing belongs are examined. A barking dog at the gate is not touched.">
        {d.slots.length ? (
          <ul className="space-y-1.5 text-sm">
            {d.slots.map((s) => (
              <li key={`${s.token}-${s.trigger}`}>
                <span className="font-mono font-medium">{s.token}</span>: {s.kind.replace(/_/g, " ")} spot (after “{s.trigger}”), expects {s.expects.join(" or ") || "a word of this kind"}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No critical spot here: the text is passed through as it is.</p>
        )}
      </Stage>
      <Stage
        n={4}
        title={STAGES[3]}
        blurb={d.path === "voice"
          ? "Voice path: a transcript is trusted unless a critical word fits its sentence badly. Sound-alike words from the domain lists are scored (how common, how well it fits, how close in sound, with the accent pack's swaps made cheaper)."
          : "Typed path: undo the accent swaps in the spelling to find real words, then score them the same way. Nothing here calls an LLM."}
      >
        {d.examined.length ? (
          <ul className="space-y-3">
            {d.examined.map((e, i) => {
              const dec = DECISION[e.decision] ?? DECISION.keep;
              const top = Math.max(1, ...e.candidates.map((c) => c.score), e.original_score);
              return (
                <li key={`${e.token}-${i}`} className="rounded-xl border border-border p-3" data-testid={`examined-${e.token}`}>
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-base font-semibold">{e.token}</span>
                    <span className="text-xs text-muted-foreground">in a {e.slot.replace(/_/g, " ")} spot</span>
                    <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", dec.cls)}>{dec.label}{e.best && e.decision === "rewrite" ? `: ${e.best}` : ""}</span>
                  </p>
                  {e.candidates.length > 0 && (
                    <ul className="mt-2 space-y-1" aria-label={`Scores for ${e.token}`}>
                      <li className="flex items-center gap-2 text-xs"><span className="w-20 shrink-0 font-mono">{e.token} (as written)</span><span className="h-2 rounded bg-muted-foreground/40" style={{ width: `${Math.max(2, (e.original_score / top) * 60)}%` }} /> <span>{e.original_score.toFixed(2)}</span></li>
                      {e.candidates.map((c) => (
                        <li key={c.word} className="flex items-center gap-2 text-xs"><span className="w-20 shrink-0 font-mono">{c.word}</span><span className="h-2 rounded bg-primary" style={{ width: `${Math.max(2, (Math.max(c.score, 0) / top) * 60)}%` }} /> <span>{c.score.toFixed(2)}</span></li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-2 text-sm text-muted-foreground">{dec.why(e.margin)}</p>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Nothing needed a decision.</p>
        )}
      </Stage>
      <Stage n={5} title={STAGES[4]} blurb="The words as the decoder read them, and the plain English (number words as digits, local phrases explained).">
        <ul className="flex flex-wrap gap-1.5">
          {d.effective_words.map((w, i) => (
            <Chip key={i} className={w !== d.tokens[i]?.text.toLowerCase() ? "bg-teal-soft text-primary" : undefined}>{w}</Chip>
          ))}
        </ul>
        <p className="mt-3 text-lg" data-testid="inspector-plain">{d.card.plain_english}</p>
      </Stage>
      <Stage n={6} title={STAGES[5]} blurb="Read by rules from the words as meant. A negation is always kept. If a question is open, the slot it touches stays empty: no silent guess.">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-base">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="font-medium">{v ?? "-"}</dd>
            </div>
          ))}
        </dl>
        {d.card.clarify.map((q) => (
          <p key={q.question} className="mt-3 rounded-xl bg-unclear-soft px-3 py-2 text-unclear-ink">Question instead of a guess: <strong>{q.question}</strong></p>
        ))}
      </Stage>
    </div>
  );
}

/** How Decode works: type any text and watch every stage happen. Deterministic rules, no model: this is the proof that it is not a wrapper around an LLM. */
export function DecodeInspector() {
  const [text, setText] = useState("");
  const [accent, setAccent] = useState<AccentHint | "">("");
  const [path, setPath] = useState<"typed" | "voice">("typed");
  const ex = useDecodeExamples();
  const run = useMutation({
    mutationFn: (b: { text: string; accent: AccentHint | ""; path: "typed" | "voice" }) =>
      withWake(() => api.inspect({ text: b.text, accent_hint: b.accent || undefined, path: b.path })),
  });
  return (
    <div className="space-y-5">
      <form
        className="card-soft space-y-3 p-4 sm:p-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) run.mutate({ text: text.trim(), accent, path });
        }}
      >
        <label htmlFor="ins-text" className="text-sm font-medium text-muted-foreground">Any message (English as heard or typed)</label>
        <Textarea id="ins-text" value={text} onChange={(e) => setText(e.target.value)} maxLength={500} className="min-h-24 text-base" placeholder="Type a message, or tap an example below" />
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="ins-accent" className="text-sm font-medium text-muted-foreground">Who is speaking?</label>
            <select id="ins-accent" value={accent} onChange={(e) => setAccent(e.target.value as AccentHint | "")} className="mt-1 block h-12 w-full rounded-xl border-2 border-input bg-card px-3 text-base">
              {ACCENTS.map((a) => (
                <option key={a.id} value={a.id}>{a.label}</option>
              ))}
            </select>
          </div>
          <fieldset>
            <legend className="text-sm font-medium text-muted-foreground">The text came from</legend>
            <div className="mt-1 flex gap-2">
              {(["typed", "voice"] as const).map((p) => (
                <button key={p} type="button" aria-pressed={path === p} onClick={() => setPath(p)}
                  className={cn("h-12 flex-1 rounded-xl border-2 px-3 text-base", path === p ? "border-primary bg-teal-soft font-medium" : "border-input bg-card")}>
                  {p === "typed" ? "Typed (WhatsApp)" : "Speech-to-text"}
                </button>
              ))}
            </div>
          </fieldset>
        </div>
        {ex.data && (
          <ul className="flex flex-wrap gap-2" aria-label="Examples">
            {ex.data.examples.map((e) => (
              <li key={e.id}>
                <button type="button" onClick={() => { setText(e.request.text); setAccent((e.request.accent_hint ?? "") as AccentHint | ""); run.mutate({ text: e.request.text, accent: (e.request.accent_hint ?? "") as AccentHint | "", path }); }}
                  className="min-h-11 rounded-full border border-border bg-card px-4 text-sm font-medium hover:bg-muted">{e.label}</button>
              </li>
            ))}
          </ul>
        )}
        <Button type="submit" className="h-12 px-6 text-base" disabled={run.isPending || !text.trim()}>Show the stages</Button>
      </form>
      {run.isError && <ErrorState message={(run.error as Error).message} onRetry={() => run.mutate({ text, accent, path })} />}
      {!run.data && !run.isPending && !run.isError && <p className="text-muted-foreground" data-testid="inspector-empty">Nothing has been decoded yet. Type a message or tap an example, then choose “Show the stages”.</p>}
      {run.data && !run.isError && <Stages d={run.data} />}
      <p className="text-sm text-muted-foreground">No language model is used for any of these stages: the same text always gives the same answer. (An LLM is only ever used, optionally, to translate the finished card.)</p>
    </div>
  );
}
