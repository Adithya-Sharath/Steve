"use client";

import { motion, useInView, useScroll, useSpring, type Variants } from "framer-motion";
import { ArrowUpRight, Check, HeartPulse, Languages, ListChecks, MessageSquareText, Mic, TriangleAlert, Users, type LucideIcon } from "lucide-react";
import { useRef } from "react";
import { NumberTicker } from "@/components/metric-tile";
import { StatusBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------------------------------------
   The problem: a stats bento. Layout and the "tinted fill rises inside each card" idea are adapted from the 21st.dev
   "Number Ticker" analytics-cards demo (danielpetho); colours are OUR status tokens, so it follows light/dark, and
   the fill is static under prefers-reduced-motion.
   ------------------------------------------------------------------------------------------------ */
type Tone = "wrong" | "understood" | "unclear" | "teal";
const TONE: Record<Tone, { soft: string; edge: string }> = {
  wrong: { soft: "var(--wrong-soft)", edge: "var(--wrong)" },
  understood: { soft: "var(--understood-soft)", edge: "var(--understood)" },
  unclear: { soft: "var(--unclear-soft)", edge: "var(--unclear)" },
  teal: { soft: "var(--teal-soft)", edge: "var(--teal)" },
};

interface Stat {
  value: number;
  decimals: number;
  prefix?: string;
  suffix: string;
  label: string;
  text: string;
  src: string;
  href: string;
  icon: LucideIcon;
  tone: Tone;
  big?: boolean;
  wide?: boolean;
}

const STATS: Stat[] = [
  {
    value: 19, decimals: 0, suffix: "%", label: "Wrong answers on labels", icon: TriangleAlert, tone: "wrong", big: true,
    text: "of patients’ answers about their own prescription labels were wrong. Dose (52%) and frequency (28%) errors dominate.",
    src: "AAFP, 2007", href: "https://www.aafp.org/pubs/afp/issues/2007/0615/p1851a.html",
  },
  {
    value: 11.9, decimals: 1, suffix: "%", label: "With teach-back", icon: HeartPulse, tone: "understood",
    text: "comprehension deficits, down from 49% (483-patient emergency department study). It excluded patients with language barriers.",
    src: "Int J Emerg Med", href: "https://link.springer.com/article/10.1186/s12245-020-00306-9",
  },
  {
    value: 12, decimals: 0, prefix: "5–", suffix: " pts", label: "LLM F1 penalty", icon: Languages, tone: "unclear",
    text: "worse for LLMs on romanized Indian-language health messages than on native script, because of spelling noise.",
    src: "arXiv 2512.10780", href: "https://arxiv.org/html/2512.10780v1",
  },
  {
    value: 38, decimals: 0, prefix: "~", suffix: "%", label: "of UAE residents", icon: Users, tone: "teal", wide: true,
    text: "are Indian; Pakistanis ~17%, Bangladeshis ~7%, Filipinos ~7%. Most write their languages in Latin script.",
    src: "GMI 2026", href: "https://www.globalmediainsight.com/blog/uae-population-statistics/",
  },
];

function StatCard({ s, index }: { s: Stat; index: number }) {
  const tone = TONE[s.tone];
  const Icon = s.icon;
  return (
    <motion.figure
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -3 }}
      className={cn(
        "card-soft group relative flex flex-col justify-between overflow-hidden p-6",
        s.big && "md:col-span-2 md:row-span-2 md:p-8",
        s.wide && "md:col-span-3",
        !s.big && !s.wide && "min-h-56",
      )}
    >
      {/* the tinted fill that rises from the bottom edge when the card scrolls in */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-3/5 origin-bottom"
        style={{ background: `linear-gradient(to top, ${tone.soft}, transparent)` }}
        initial={{ scaleY: 0, opacity: 0 }}
        whileInView={{ scaleY: 1, opacity: 1 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 1.1, delay: 0.2 + index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      />
      <span aria-hidden className="absolute inset-x-0 bottom-0 h-0.5 opacity-70" style={{ background: tone.edge }} />
      <div className="relative flex items-center justify-between gap-3 text-sm text-muted-foreground">
        <span>{s.label}</span>
        <span className="grid size-8 place-items-center rounded-xl bg-card/80 ring-1 ring-border" style={{ color: tone.edge }}>
          <Icon className="size-4" aria-hidden />
        </span>
      </div>
      <div className={cn("relative mt-6", s.wide && "md:flex md:items-end md:gap-10")}>
        <p className={cn("font-display leading-none", s.big ? "text-8xl md:text-9xl" : s.wide ? "text-7xl md:shrink-0" : "text-6xl")} style={{ color: "var(--foreground)" }}>
          <NumberTicker value={s.value} decimals={s.decimals} prefix={s.prefix} suffix={s.suffix} delay={index * 0.12} />
        </p>
        <figcaption className={cn("mt-4 leading-relaxed text-foreground/85", s.big ? "max-w-md text-lg" : s.wide ? "max-w-xl text-base md:mt-0" : "text-[15px]")}>
          {s.text}{" "}
          <a href={s.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 whitespace-nowrap text-sm text-primary underline underline-offset-4">
            {s.src}
            <ArrowUpRight className="size-3.5" aria-hidden />
          </a>
        </figcaption>
      </div>
    </motion.figure>
  );
}

export function ProblemStats() {
  return (
    <div className="mt-10 grid gap-4 md:grid-cols-3 md:grid-rows-[auto_auto]">
      {STATS.map((s, i) => (
        <StatCard key={s.src} s={s} index={i} />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------------------------------------
   How it works: a vertical timeline (numbered nodes on a rail whose fill follows your scroll), inspired by the
   structure of 21st.dev "Vertical How It Works Timeline" (ln-dev7); built with our tokens. Each step carries a
   small real example so the section teaches instead of just listing.
   ------------------------------------------------------------------------------------------------ */
interface Step {
  icon: LucideIcon;
  title: string;
  body: string;
  example: React.ReactNode;
}

const mono = "rounded-lg bg-muted/70 px-2.5 py-1.5 font-mono text-[13px] text-foreground/85";
const STEPS: Step[] = [
  {
    icon: MessageSquareText,
    title: "Write the message",
    body: "Any important instruction. In your own language, however you write it.",
    example: <p className={mono}>Take 2 tablets after food, twice a day, for 5 days. Stop and call us if you get a rash.</p>,
  },
  {
    icon: ListChecks,
    title: "Confirm the key facts",
    body: "Doses, dates, amounts and “if … then” rules become typed facts. You confirm them.",
    example: (
      <ul className="flex flex-wrap gap-1.5" aria-label="Example facts">
        {["2 tablets", "after food", "twice a day", "5 days", "stop if rash"].map((f) => (
          <li key={f} className="rounded-full border border-border bg-card px-2.5 py-1 text-xs">{f}</li>
        ))}
      </ul>
    ),
  },
  {
    icon: Mic,
    title: "Reader explains it back",
    body: "By voice or text, in any mix, spelled any way. They never see a score.",
    example: <p className={mono}>randu gulika, food kazhinju, raavile vaikittu, oru week</p>,
  },
  {
    icon: Check,
    title: "See it fact by fact",
    body: "Understood, wrong, missing, negated or unclear, with the exact words as evidence. Re-explain only what failed.",
    example: (
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge status="understood" size="sm" animate={false} />
        <StatusBadge status="wrong" size="sm" animate={false} />
        <StatusBadge status="missing" size="sm" animate={false} />
        <span className="font-mono text-xs text-muted-foreground">“oru week” = 7 days, not 5</span>
      </div>
    ),
  },
];

const nodeVariants: Variants = {
  off: { scale: 1 },
  on: { scale: [0.8, 1.14, 1], transition: { duration: 0.45, ease: "easeOut" } },
};

function StepItem({ step, index }: { step: Step; index: number }) {
  const ref = useRef<HTMLLIElement>(null);
  const active = useInView(ref, { margin: "0px 0px -45% 0px", once: true });
  const Icon = step.icon;
  return (
    <motion.li
      ref={ref}
      initial={{ opacity: 0, x: 18 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
      className="relative pl-16"
    >
      <motion.span
        variants={nodeVariants}
        animate={active ? "on" : "off"}
        aria-hidden
        className={cn(
          "absolute left-0 top-1 grid size-10 place-items-center rounded-full border font-mono text-sm font-semibold transition-colors duration-300",
          active ? "border-primary bg-primary text-primary-foreground shadow-[0_6px_16px_-6px_var(--primary)]" : "border-border bg-card text-muted-foreground",
        )}
      >
        {String(index + 1).padStart(2, "0")}
      </motion.span>
      <div className="card-soft p-5 transition-shadow duration-300 hover:shadow-[0_18px_40px_-22px_color-mix(in_oklch,var(--foreground)_40%,transparent)]">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-teal-soft text-primary">
            <Icon className="size-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <h3 className="font-medium">{step.title}</h3>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
          </div>
        </div>
        <div className="mt-4 sm:pl-[3.25rem]">{step.example}</div>
      </div>
    </motion.li>
  );
}

export function HowSteps() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 70%", "end 55%"] });
  const fill = useSpring(scrollYProgress, { stiffness: 120, damping: 24, mass: 0.4 });
  return (
    <div ref={ref} className="relative mt-10 max-w-3xl">
      {/* dashed rail + a solid fill that follows the scroll (full and static under reduced motion, by CSS only, so server and client HTML never differ) */}
      <span aria-hidden className="absolute bottom-6 left-5 top-6 w-px border-l border-dashed border-border" />
      <motion.span
        aria-hidden
        className="absolute bottom-6 left-5 top-6 w-0.5 origin-top -translate-x-1/2 rounded-full bg-primary/70 motion-reduce:[transform:translateX(-50%)_scaleY(1)!important]"
        style={{ scaleY: fill }}
      />
      <ol className="space-y-6">
        {STEPS.map((s, i) => (
          <StepItem key={s.title} step={s} index={i} />
        ))}
      </ol>
    </div>
  );
}
