"use client";

import { motion } from "framer-motion";
import { Copy } from "lucide-react";
import { StatusBadge } from "@/components/status-badge";
import { FACT_ICON, FACT_TYPE_LABEL, STATUS_META } from "@/lib/status";
import type { Fact, FactResult } from "@/lib/types";
import { cn } from "@/lib/utils";

export function MatchedTokens({ result }: { result: FactResult }) {
  const terms = result.matched_terms.filter((t) => t.category !== "filler");
  if (!terms.length) return null;
  return (
    <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Words we recognised">
      {terms.map((t, i) => (
        <li
          key={`${t.token}-${i}`}
          className="rounded-md border border-border bg-muted/60 px-1.5 py-0.5 font-mono text-[11px] leading-5 text-muted-foreground"
          title={`${t.category} · matched by ${t.kind}`}
        >
          {t.token} <span aria-hidden>→</span> <span className="text-foreground">{t.lexeme}</span> · {t.lang} · {t.score}
        </li>
      ))}
    </ul>
  );
}

export function FactCard({
  fact,
  result,
  pending = false,
  active = false,
  onHover,
  showTokens = true,
}: {
  fact: Fact;
  result?: FactResult | null;
  pending?: boolean;
  active?: boolean;
  onHover?: (id: string | null) => void;
  showTokens?: boolean;
}) {
  const Icon = FACT_ICON[fact.type];
  const meta = result ? STATUS_META[result.status] : null;
  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ type: "spring", stiffness: 380, damping: 32 }}
      onMouseEnter={() => onHover?.(fact.id)}
      onMouseLeave={() => onHover?.(null)}
      onFocus={() => onHover?.(fact.id)}
      onBlur={() => onHover?.(null)}
      tabIndex={onHover ? 0 : undefined}
      aria-label={`${fact.label}: ${result ? result.status : pending ? "waiting for a reply" : "not checked yet"}`}
      className={cn(
        "list-none rounded-2xl border bg-card p-4 transition-shadow",
        meta ? meta.border : "border-border",
        active && "shadow-[0_0_0_3px_color-mix(in_oklch,var(--ring)_35%,transparent)]",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl",
            meta ? cn(meta.soft, meta.text) : "bg-muted text-muted-foreground",
          )}
        >
          <Icon className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <div className="min-w-0">
              <p className="truncate font-medium leading-tight">{fact.label}</p>
              <p className="text-xs text-muted-foreground">{FACT_TYPE_LABEL[fact.type]}</p>
            </div>
            {result ? (
              <StatusBadge status={result.status} />
            ) : pending ? (
              <span className="shimmer h-6 w-24 rounded-full" role="status" aria-label="Waiting for a reply" />
            ) : null}
          </div>
          {result?.flags?.includes("copied") && (
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-unclear-soft px-2 py-0.5 text-xs font-medium text-unclear-ink">
              <Copy className="size-3" aria-hidden /> copied from the message
            </p>
          )}
          {result && (
            <motion.p
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 }}
              className="mt-2 text-sm leading-relaxed text-foreground/85"
            >
              {result.reason}
            </motion.p>
          )}
          {result && showTokens && <MatchedTokens result={result} />}
          {pending && !result && <div className="shimmer mt-3 h-3 w-4/5 rounded" aria-hidden />}
        </div>
      </div>
    </motion.li>
  );
}
