import type { Span, Status } from "./types";

/** Engine offsets are Python code points, JS strings are UTF-16: always slice via code points. */
export function toCodePoints(s: string): string[] {
  return Array.from(s);
}

export interface Highlight {
  id: string;
  span: Span;
  /** undefined = neutral (no result yet) */
  status?: Status;
}

export interface Segment {
  text: string;
  ids: string[];
}

export function segmentText(text: string, highlights: Highlight[]): Segment[] {
  const cps = toCodePoints(text);
  const cover: string[][] = cps.map(() => []);
  for (const h of highlights) {
    for (let i = Math.max(0, h.span.start); i < Math.min(cps.length, h.span.end); i++) {
      if (!cover[i].includes(h.id)) cover[i].push(h.id);
    }
  }
  const out: Segment[] = [];
  let cur: Segment | null = null;
  for (let i = 0; i < cps.length; i++) {
    const key = cover[i].join("|");
    if (cur && cur.ids.join("|") === key) {
      cur.text += cps[i];
    } else {
      cur = { text: cps[i], ids: cover[i] };
      out.push(cur);
    }
  }
  return out;
}

/** Highlight a fact's evidence inside the ORIGINAL sender message (matching by text, not offsets). */
export function findAll(text: string, needle: string): [number, number][] {
  if (!needle) return [];
  const lower = text.toLowerCase();
  const n = needle.toLowerCase();
  const out: [number, number][] = [];
  let i = 0;
  while ((i = lower.indexOf(n, i)) !== -1) {
    out.push([i, i + n.length]);
    i += n.length;
  }
  return out;
}
