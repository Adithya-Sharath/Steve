"use client";

import { useReducedMotionSafe } from "@/hooks/use-reduced-motion";
import { animate, motion, useInView, useMotionValue, useTransform } from "framer-motion";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Counts up when scrolled into view. Approach adapted from the 21st.dev "Number Ticker" (danielpetho/basic-number-ticker):
 * a motion value is tweened and rendered directly, so the number updates without a React re-render per frame.
 * Ours adds decimals/prefix/suffix, in-view triggering, an optional `delay`, and reduced-motion (shows the final value).
 */
export function NumberTicker({
  value,
  decimals = 0,
  suffix = "",
  prefix = "",
  duration = 1.6,
  delay = 0,
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  duration?: number;
  delay?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotionSafe();
  const count = useMotionValue(0);
  const text = useTransform(count, (v) => `${prefix}${v.toFixed(decimals)}${suffix}`);

  useEffect(() => {
    if (reduce) {
      count.set(value);
      return;
    }
    if (!inView) return;
    const controls = animate(count, value, { duration, delay, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [inView, reduce, value, duration, delay, count]);

  return (
    <motion.span ref={ref} className="tabular-nums">
      {text}
    </motion.span>
  );
}

export function MetricTile({
  label,
  value,
  decimals = 0,
  suffix = "",
  sub,
  tone = "neutral",
  emphasis = false,
  empty,
  className,
}: {
  label: string;
  value: number | null | undefined;
  decimals?: number;
  suffix?: string;
  sub?: string;
  tone?: "neutral" | "good" | "bad";
  emphasis?: boolean;
  empty?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "card-soft relative overflow-hidden p-5",
        emphasis && "border-primary/40 ring-1 ring-primary/25",
        className,
      )}
    >
      {emphasis && <div aria-hidden className="pointer-events-none absolute -right-8 -top-8 size-28 rounded-full bg-primary/10 blur-2xl" />}
      <p className="text-sm text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1 font-display leading-none",
          emphasis ? "text-6xl" : "text-5xl",
          tone === "good" && "text-understood-ink",
          tone === "bad" && "text-wrong-ink",
        )}
      >
        {value == null ? <span className="text-3xl text-muted-foreground">{empty ?? "n/a"}</span> : <NumberTicker value={value} decimals={decimals} suffix={suffix} />}
      </p>
      {sub && <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{sub}</p>}
    </div>
  );
}
