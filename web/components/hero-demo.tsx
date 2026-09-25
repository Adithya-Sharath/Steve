"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Mic } from "lucide-react";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import type { Status } from "@/lib/types";

const MESSAGE = "Take 2 tablets after food, twice a day, for 5 days. Stop taking them and call us if you get a rash.";
const REPLY = "randu gulika, food kazhinju, raavile vaikittu, oru week";

// These are the engine's real results for this exact reply (see data/scenarios.json, pharmacy · subtle_mistake).
const CHIPS: { label: string; detail: string; status: Status }[] = [
  { label: "Dose", detail: "randu gulika = 2 tablets", status: "understood" },
  { label: "Timing", detail: "food kazhinju = after food", status: "understood" },
  { label: "Frequency", detail: "raavile vaikittu = 2 a day", status: "understood" },
  { label: "Duration", detail: "“oru week” = 7 days ≠ 5 days", status: "wrong" },
  { label: "Rash warning", detail: "never mentioned", status: "missing" },
];

export function HeroDemo() {
  const reduce = useReducedMotion();
  const [animPhase, setPhase] = useState(0); // 0 msg, 1 typing reply, 2.. chips
  const [animTyped, setTyped] = useState(0);
  const [animChips, setChips] = useState(0);
  // reduced motion: show the finished state statically
  const phase = reduce ? 2 : animPhase;
  const typed = reduce ? REPLY.length : animTyped;
  const chips = reduce ? CHIPS.length : animChips;

  useEffect(() => {
    if (reduce) return;
    let alive = true;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const at = (ms: number, fn: () => void) => timers.push(setTimeout(() => alive && fn(), ms));
    const run = () => {
      setPhase(0);
      setTyped(0);
      setChips(0);
      at(900, () => setPhase(1));
      for (let i = 1; i <= REPLY.length; i++) at(1500 + i * 38, () => setTyped(i));
      const doneTyping = 1500 + REPLY.length * 38 + 500;
      at(doneTyping, () => setPhase(2));
      CHIPS.forEach((_, i) => at(doneTyping + 350 + i * 650, () => setChips(i + 1)));
      at(doneTyping + 350 + CHIPS.length * 650 + 4200, run);
    };
    run();
    return () => {
      alive = false;
      timers.forEach(clearTimeout);
    };
  }, [reduce]);

  return (
    <div className="card-soft mx-auto w-full max-w-xl overflow-hidden" role="img" aria-label="Animated example: a pharmacist's message, a Manglish voice reply, and fact-by-fact results">
      <div className="flex items-center gap-2 border-b border-border bg-muted/50 px-4 py-2.5 text-xs text-muted-foreground">
        <span className="size-2 rounded-full bg-understood" aria-hidden /> Al Noor Pharmacy · WhatsApp
      </div>
      <div className="min-h-[19rem] space-y-3 bg-[color-mix(in_oklch,var(--teal-soft)_45%,var(--card))] p-4" aria-hidden>
        <motion.div
          initial={{ opacity: 0, y: 10, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          className="max-w-[88%] rounded-2xl rounded-tl-sm bg-card px-3.5 py-2.5 text-sm shadow-sm"
        >
          {MESSAGE}
        </motion.div>
        <AnimatePresence>
          {phase >= 1 && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              className="ml-auto max-w-[88%] rounded-2xl rounded-tr-sm bg-[color-mix(in_oklch,var(--understood)_22%,var(--card))] px-3.5 py-2.5 text-sm shadow-sm"
            >
              <span className="mb-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <Mic className="size-3" /> voice reply · Manglish
              </span>
              <span className="font-mono text-[13px]">
                {REPLY.slice(0, typed)}
                {typed < REPLY.length && <span className="ml-0.5 inline-block h-3.5 w-px animate-pulse bg-foreground align-middle" />}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
        <ul className="grid gap-1.5 pt-1">
          {CHIPS.slice(0, chips).map((c) => (
            <motion.li
              key={c.label}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: "spring", stiffness: 420, damping: 28 }}
              className="flex items-center justify-between gap-3 rounded-xl border border-border bg-card px-3 py-2"
            >
              <span className="min-w-0 text-sm">
                <span className="font-medium">{c.label}</span>
                <span className="ml-2 truncate font-mono text-xs text-muted-foreground">{c.detail}</span>
              </span>
              <StatusBadge status={c.status} size="sm" />
            </motion.li>
          ))}
        </ul>
      </div>
      <p className="border-t border-border px-4 py-2.5 text-xs text-muted-foreground">
        The reader only sees a thank-you. The sender sees exactly which facts landed.
      </p>
    </div>
  );
}
