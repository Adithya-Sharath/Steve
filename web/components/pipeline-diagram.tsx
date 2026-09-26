"use client";

import { useReducedMotionSafe } from "@/hooks/use-reduced-motion";
import { motion } from "framer-motion";
import { AudioLines, Ban, Boxes, Eraser, Scale, ShieldCheck, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

export interface Stage {
  icon: LucideIcon;
  title: string;
  body: string;
  example: string;
}

export const PIPELINE: Stage[] = [
  { icon: Eraser, title: "Clean", body: "Normalise digits and quotes, tokenize. Every token keeps its character offsets.", example: "RANDU gulika 😊 → randu · gulika" },
  { icon: AudioLines, title: "Match by ear", body: "Exact, suffix, sound-key and guarded fuzzy matching against a multilingual lexicon.", example: "rendu / rndu / randu → 2 (ml)" },
  { icon: Ban, title: "Negation", body: "Per-language scope rules decide what a “don’t / venda / mat / huwag” is attached to.", example: "rash vannalum nirthanda → don’t stop" },
  { icon: Boxes, title: "Fill slots", body: "Numbers only count next to an anchor word: unit, counter, duration or currency.", example: "randu gulika → dose 2 tablet" },
  { icon: Scale, title: "Compare", body: "Exact equality on numbers, dates and durations. Sets for timing. No LLM.", example: "oru week = 7 days ≠ 5 days" },
  { icon: ShieldCheck, title: "Decide", body: "Low confidence never becomes “understood”. Each result carries evidence + a reason.", example: "wrong · 'oru week' · conf 1.00" },
];

export function PipelineDiagram({
  stages = PIPELINE,
  active,
  autoplay = true,
  onSelect,
  className,
}: {
  stages?: Stage[];
  active?: number;
  autoplay?: boolean;
  onSelect?: (i: number) => void;
  className?: string;
}) {
  const reduce = useReducedMotionSafe();
  const [auto, setAuto] = useState(0);
  useEffect(() => {
    if (active != null || !autoplay || reduce) return;
    const t = setInterval(() => setAuto((a) => (a + 1) % stages.length), 1900);
    return () => clearInterval(t);
  }, [active, autoplay, reduce, stages.length]);
  const cur = active ?? auto;
  return (
    <ol className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {stages.map((s, i) => {
        const on = i === cur;
        const Icon = s.icon;
        return (
          <motion.li
            key={s.title}
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ delay: i * 0.06, type: "spring", stiffness: 260, damping: 26 }}
            className={cn(
              "relative rounded-2xl border bg-card p-4 transition-all duration-300",
              on ? "border-primary/60 shadow-[0_10px_30px_-14px_color-mix(in_oklch,var(--primary)_55%,transparent)]" : "border-border",
            )}
            aria-current={on ? "step" : undefined}
          >
            <button type="button" disabled={!onSelect} onClick={() => onSelect?.(i)} className="block w-full text-left disabled:cursor-default">
            <div className="flex items-center gap-3">
              <span className={cn("grid size-9 place-items-center rounded-xl transition-colors", on ? "bg-primary text-primary-foreground" : "bg-teal-soft text-primary")}>
                <Icon className="size-[18px]" aria-hidden />
              </span>
              <div>
                <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Stage {i + 1}</p>
                <span className="block font-medium leading-tight">{s.title}</span>
              </div>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
            <p className="mt-3 rounded-lg bg-muted/70 px-2.5 py-1.5 font-mono text-xs text-foreground/80">{s.example}</p>
            </button>
            {on && !reduce && (
              <motion.span layoutId="pipeline-dot" className="absolute -right-1.5 -top-1.5 size-3 rounded-full bg-primary" aria-hidden />
            )}
          </motion.li>
        );
      })}
    </ol>
  );
}
