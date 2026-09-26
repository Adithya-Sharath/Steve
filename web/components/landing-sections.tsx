"use client";

import { motion } from "framer-motion";
import { ArrowUpRight, Check, X } from "lucide-react";
import Link from "next/link";
import { LlmToggle, useHealth } from "@/components/llm-toggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const fade = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] as const },
};

export function SectionHead({ eyebrow, title, body, className }: { eyebrow: string; title: React.ReactNode; body?: string; className?: string }) {
  return (
    <motion.div {...fade} className={cn("max-w-2xl", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">{eyebrow}</p>
      <h2 className="mt-2 font-display text-4xl leading-[1.05] sm:text-5xl">{title}</h2>
      {body && <p className="mt-3 text-lg text-muted-foreground">{body}</p>}
    </motion.div>
  );
}

export { HowSteps, ProblemStats } from "./landing-stats-steps";

export function WhyNotTranslate() {
  const rows: [string, string][] = [
    ["Rewrites the reply into “proper” English", "Reads the reply exactly as written"],
    ["Forces people back into the one clean version", "Meets them in the way they actually write"],
    ["Loses “oru week”, keeps a fluent guess", "Turns “oru week” into 7 days and compares it to 5"],
    ["Checks the sender’s words", "Checks the reader’s understanding"],
  ];
  return (
    <div className="mt-10 overflow-hidden rounded-3xl border border-border bg-card">
      <div className="grid grid-cols-2 border-b border-border bg-muted/50 text-sm font-medium">
        <p className="flex items-center gap-2 p-4 text-wrong-ink"><X className="size-4" aria-hidden /> Translate / normalise</p>
        <p className="flex items-center gap-2 border-l border-border p-4 text-understood-ink"><Check className="size-4" aria-hidden /> Teach-back check</p>
      </div>
      {rows.map(([a, b], i) => (
        <motion.div key={a} {...fade} transition={{ ...fade.transition, delay: i * 0.06 }} className="grid grid-cols-2 border-b border-border last:border-0">
          <p className="p-4 text-[15px] text-muted-foreground">{a}</p>
          <p className="border-l border-border p-4 text-[15px]">{b}</p>
        </motion.div>
      ))}
    </div>
  );
}

export function NotAWrapper() {
  const { data } = useHealth();
  const rows = [
    ["Numbers, doses, dates, durations, negations", "Deterministic code in engine/ (tested)"],
    ["Understood / wrong / missing", "Rules + exact compare, never an LLM"],
    ["Extracting facts from your message", "Built-in extractor (LLM optional, you confirm)"],
    ["Speech-to-text", "Optional. Typed replies always work"],
  ];
  return (
    <div className="mt-10 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
      <div className="card-soft divide-y divide-border">
        {rows.map(([a, b]) => (
          <div key={a} className="grid gap-1 p-4 sm:grid-cols-2 sm:gap-4">
            <p className="text-sm text-muted-foreground">{a}</p>
            <p className="text-sm font-medium">{b}</p>
          </div>
        ))}
      </div>
      <motion.div {...fade} className="card-soft flex flex-col justify-between gap-4 p-6">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">The wrapper test</p>
          <p className="mt-2 font-display text-3xl leading-tight">Turn the LLM off. Nothing breaks.</p>
          <p className="mt-2 text-sm text-muted-foreground">
            The operator can switch the LLM helper off. Compose, reply and check still work, because the judge is our engine, not a model.
          </p>
        </div>
        <div className="flex items-center justify-between rounded-2xl border border-border bg-muted/50 p-4">
          <LlmToggle />
          <span className="text-sm text-muted-foreground" aria-live="polite">
            {data ? (data.llm_enabled ? "LLM on (helper only)" : "LLM off") : "server offline"}
          </span>
        </div>
        <Link href="/how-it-works" className={cn(buttonVariants({ variant: "outline" }), "self-start")}>
          See it run stage by stage <ArrowUpRight />
        </Link>
      </motion.div>
    </div>
  );
}

const LANGS = [
  { name: "Manglish", sub: "Malayalam in Latin script", eg: "randu gulika, food kazhinju", voice: true },
  { name: "Hinglish", sub: "Hindi / Urdu in Latin script", eg: "do goli khane ke baad", voice: true },
  { name: "Arabizi", sub: "Gulf Arabic with digits", eg: "ithnain habba ba3d al akl", voice: false },
  { name: "Taglish", sub: "Tagalog + English", eg: "dalawang tableta pagkatapos kumain", voice: false },
];

export function Languages() {
  return (
    <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {LANGS.map((l, i) => (
        <motion.div key={l.name} {...fade} transition={{ ...fade.transition, delay: i * 0.07 }} className="card-soft p-5">
          <h3 className="font-display text-3xl">{l.name}</h3>
          <p className="text-sm text-muted-foreground">{l.sub}</p>
          <p className="mt-4 rounded-lg bg-muted/70 px-2.5 py-2 font-mono text-[13px]">{l.eg}</p>
          <p className="mt-3 text-xs text-muted-foreground">{l.voice ? "Typed and voice replies" : "Typed replies (voice: roadmap)"}</p>
        </motion.div>
      ))}
    </div>
  );
}

export function FinalCta() {
  return (
    <div className="card-soft mx-auto max-w-3xl px-6 py-14 text-center">
      <h2 className="font-display text-4xl sm:text-5xl">Stop guessing what “ok 👍” meant.</h2>
      <p className="mx-auto mt-3 max-w-lg text-muted-foreground">Run the pharmacy scenario end to end in about a minute. No account, no keys.</p>
      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Link href="/demo" className={cn(buttonVariants({ size: "lg" }), "h-11 px-5 text-base")}>Try the demo</Link>
        <Link href="/app/new" className={cn(buttonVariants({ size: "lg", variant: "outline" }), "h-11 px-5 text-base")}>Send your own message</Link>
      </div>
    </div>
  );
}

export { Button };
