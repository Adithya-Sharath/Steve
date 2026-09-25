"use client";

import { useMemo } from "react";
import { STATUS_META } from "@/lib/status";
import { segmentText, type Highlight } from "@/lib/spans";
import { cn } from "@/lib/utils";

/**
 * The reader's words, VERBATIM in a mono face. Evidence spans are highlighted in the matching status colour with a
 * left-to-right sweep. Hover a span to focus its fact card (and vice versa via `activeId`).
 */
export function Transcript({
  text,
  highlights,
  activeId,
  onHover,
  className,
}: {
  text: string;
  highlights: Highlight[];
  activeId?: string | null;
  onHover?: (id: string | null) => void;
  className?: string;
}) {
  const segments = useMemo(() => segmentText(text, highlights), [text, highlights]);
  const statusById = useMemo(() => new Map(highlights.map((h) => [h.id, h.status])), [highlights]);
  const neutral = { cssSoft: "var(--teal-soft)", cssVar: "var(--teal)" };
  let hi = 0;
  return (
    <p className={cn("whitespace-pre-wrap break-words font-mono text-[15px] leading-8", className)} lang="und">
      {segments.map((s, i) => {
        if (!s.ids.length) return <span key={i}>{s.text}</span>;
        const primary = s.ids.includes(activeId ?? "") ? (activeId as string) : s.ids[0];
        const status = statusById.get(primary);
        const meta = status ? STATUS_META[status] : neutral;
        const isActive = activeId != null && s.ids.includes(activeId);
        const delay = (hi++ % 8) * 90;
        return (
          <mark
            key={i}
            onMouseEnter={() => onHover?.(primary)}
            onMouseLeave={() => onHover?.(null)}
            className="hl-sweep rounded-[5px] px-0.5 text-foreground transition-[outline,box-shadow] duration-150"
            style={{
              backgroundImage: `linear-gradient(${meta.cssSoft}, ${meta.cssSoft})`,
              boxShadow: `inset 0 -2px 0 ${meta.cssVar}`,
              outline: isActive ? `2px solid ${meta.cssVar}` : "2px solid transparent",
              outlineOffset: 1,
              animationDelay: `${delay}ms`,
            }}
            data-status={status ?? "pending"}
          >
            {s.text}
          </mark>
        );
      })}
    </p>
  );
}
