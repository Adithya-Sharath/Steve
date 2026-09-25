import { Ban, Check, CircleDashed, CircleHelp, X, type LucideIcon } from "lucide-react";
import {
  Banknote,
  CalendarDays,
  Clock,
  Hourglass,
  Pill,
  Repeat,
  ShieldAlert,
} from "lucide-react";
import type { FactType, Status } from "./types";

export interface StatusMeta {
  label: string;
  short: string;
  icon: LucideIcon;
  /** static class strings so Tailwind can see them */
  chip: string;
  text: string;
  soft: string;
  border: string;
  solid: string;
  cssVar: string;
  cssSoft: string;
  blurb: string;
}

export const STATUS_ORDER: Status[] = ["wrong", "negated", "missing", "unclear", "understood"];

export const STATUS_META: Record<Status, StatusMeta> = {
  understood: {
    label: "Understood",
    short: "Understood",
    icon: Check,
    chip: "bg-understood-soft text-understood-ink border-understood/40",
    text: "text-understood-ink",
    soft: "bg-understood-soft",
    border: "border-understood/50",
    solid: "bg-understood",
    cssVar: "var(--understood)",
    cssSoft: "var(--understood-soft)",
    blurb: "Said back correctly",
  },
  wrong: {
    label: "Wrong",
    short: "Wrong",
    icon: X,
    chip: "bg-wrong-soft text-wrong-ink border-wrong/40",
    text: "text-wrong-ink",
    soft: "bg-wrong-soft",
    border: "border-wrong/50",
    solid: "bg-wrong",
    cssVar: "var(--wrong)",
    cssSoft: "var(--wrong-soft)",
    blurb: "A different value was said",
  },
  missing: {
    label: "Missing",
    short: "Missing",
    icon: CircleDashed,
    chip: "bg-missing-soft text-missing-ink border-missing/50",
    text: "text-missing-ink",
    soft: "bg-missing-soft",
    border: "border-missing/60",
    solid: "bg-missing",
    cssVar: "var(--missing)",
    cssSoft: "var(--missing-soft)",
    blurb: "Not mentioned",
  },
  negated: {
    label: "Negated",
    short: "Negated",
    icon: Ban,
    chip: "bg-negated-soft text-negated-ink border-negated/40",
    text: "text-negated-ink",
    soft: "bg-negated-soft",
    border: "border-negated/50",
    solid: "bg-negated",
    cssVar: "var(--negated)",
    cssSoft: "var(--negated-soft)",
    blurb: "Said the opposite",
  },
  unclear: {
    label: "Unclear",
    short: "Unclear",
    icon: CircleHelp,
    chip: "bg-unclear-soft text-unclear-ink border-unclear/40",
    text: "text-unclear-ink",
    soft: "bg-unclear-soft",
    border: "border-unclear/50",
    solid: "bg-unclear",
    cssVar: "var(--unclear)",
    cssSoft: "var(--unclear-soft)",
    blurb: "Can't tell for sure",
  },
};

export const FACT_ICON: Record<FactType, LucideIcon> = {
  dose: Pill,
  frequency: Repeat,
  timing: Clock,
  duration: Hourglass,
  date: CalendarDays,
  amount: Banknote,
  condition: ShieldAlert,
};

export const FACT_TYPE_LABEL: Record<FactType, string> = {
  dose: "Dose / quantity",
  frequency: "How often",
  timing: "When",
  duration: "How long",
  date: "Date / time",
  amount: "Amount",
  condition: "If … then",
};

export const LANG_LABEL: Record<string, string> = {
  manglish: "Manglish",
  hinglish: "Hinglish",
  arabizi: "Arabizi",
  taglish: "Taglish",
  english: "English",
  mixed: "Mixed",
};
