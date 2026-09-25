"use client";

import { animate, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function NumberTicker({
  value,
  decimals = 0,
  suffix = "",
  prefix = "",
  duration = 1.1,
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!inView || reduce) return;
    const c = animate(0, value, { duration, ease: [0.22, 1, 0.36, 1], onUpdate: setN });
    return () => c.stop();
  }, [inView, value, duration, reduce]);
  const shown = reduce ? value : n;
  return (
    <span ref={ref} className="tabular-nums">
      {prefix}
      {shown.toFixed(decimals)}
      {suffix}
    </span>
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
