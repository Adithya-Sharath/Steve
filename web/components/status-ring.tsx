"use client";

import { motion } from "framer-motion";
import { STATUS_META, STATUS_ORDER } from "@/lib/status";
import type { Aggregate } from "@/lib/types";

/** Segmented ring: one arc per status, centre shows understood/total. */
export function StatusRing({ aggregate, size = 64 }: { aggregate: Aggregate; size?: number }) {
  const total = Math.max(1, aggregate.total);
  const r = 26;
  const c = 2 * Math.PI * r;
  const gap = aggregate.total > 1 ? 3 : 0;
  const order = [...STATUS_ORDER].reverse(); // understood first
  const arcs = order.reduce<{ s: (typeof order)[number]; len: number; offset: number }[]>((acc, s) => {
    const n = aggregate[s] ?? 0;
    if (!n) return acc;
    const prev = acc[acc.length - 1];
    acc.push({ s, len: (n / total) * c, offset: prev ? prev.offset + prev.len : 0 });
    return acc;
  }, []);
  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${aggregate.understood} of ${aggregate.total} facts understood`}
    >
      <svg viewBox="0 0 64 64" className="-rotate-90" width={size} height={size}>
        <circle cx="32" cy="32" r={r} fill="none" stroke="var(--muted)" strokeWidth="7" />
        {arcs.map(({ s, len, offset }) => (
          <motion.circle
            key={s}
            cx="32"
            cy="32"
            r={r}
            fill="none"
            stroke={STATUS_META[s].cssVar}
            strokeWidth="7"
            strokeLinecap="butt"
            strokeDashoffset={-offset}
            initial={{ strokeDasharray: `0 ${c}` }}
            animate={{ strokeDasharray: `${Math.max(0, len - gap)} ${c}` }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          />
        ))}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center leading-none">
        <span className="text-sm font-semibold tabular-nums">
          {aggregate.understood}
          <span className="text-muted-foreground">/{aggregate.total}</span>
        </span>
      </div>
    </div>
  );
}
