import type { ConditionValue, Context, Fact, FactType } from "./types";

export const DOSE_UNITS = ["tablet", "capsule", "ml", "puff", "drop", "spoon", "bottle", "photo", "form", "copy"];
export const DURATION_UNITS = ["day", "hour", "minute"];
export const TIMING_TAGS = ["before_food", "after_food", "empty_stomach", "morning", "noon", "afternoon", "evening", "night", "bedtime"];
export const ACTIONS: ConditionValue["action"][] = ["stop", "call", "come_back", "continue", "avoid"];
export const CONTEXTS: { id: Context; label: string; emoji: string }[] = [
  { id: "pharmacy", label: "Pharmacy", emoji: "💊" },
  { id: "workplace", label: "Workplace", emoji: "🦺" },
  { id: "visa", label: "Visa / HR", emoji: "🛂" },
  { id: "school", label: "School", emoji: "🎒" },
  { id: "other", label: "Other", emoji: "✉️" },
];

const plural = (unit: string, n: number) => (n === 1 ? unit : `${unit}s`);

export function autoLabel(f: Pick<Fact, "type" | "value" | "unit">): string {
  const v = f.value;
  switch (f.type as FactType) {
    case "dose":
      return `${v} ${plural(f.unit ?? "", Number(v))}`.trim();
    case "frequency": {
      const n = Number(v);
      return n === 1 ? "once a day" : n === 2 ? "twice a day" : n === 24 ? "every hour" : `${n} times a day`;
    }
    case "timing":
      return (Array.isArray(v) ? v : [String(v)]).map((t) => t.replace("_", " ")).join(", ");
    case "duration":
      return `${v} ${plural(f.unit ?? "day", Number(v))}`;
    case "date": {
      const s = String(v);
      return /^[a-z]+$/.test(s) ? `by ${s[0].toUpperCase()}${s.slice(1)}` : `at ${s}`;
    }
    case "amount":
      return `${v} ${f.unit ?? ""}`.trim();
    case "condition": {
      const c = v as ConditionValue;
      return c.action === "avoid" ? `Do not ${c.trigger}` : `${c.action.replace("_", " ")} if ${c.trigger}`.replace(/^./, (x) => x.toUpperCase());
    }
  }
}

export function blankFact(type: FactType, existing: Fact[]): Fact {
  const n = existing.filter((f) => f.type === type).length + 1;
  const id = `${type}_${n}_${Math.random().toString(36).slice(2, 5)}`;
  const base = { id, type, critical: true } as const;
  switch (type) {
    case "dose": return { ...base, value: 1, unit: "tablet", label: "1 tablet" };
    case "frequency": return { ...base, value: 2, unit: null, label: "twice a day" };
    case "timing": return { ...base, value: "after_food", unit: null, label: "after food" };
    case "duration": return { ...base, value: 5, unit: "day", label: "5 days" };
    case "date": return { ...base, value: "thursday", unit: null, label: "by Thursday" };
    case "amount": return { ...base, value: 100, unit: "AED", label: "100 AED" };
    case "condition":
      return { ...base, value: { trigger: "rash", action: "stop", text: "Stop if you get a rash" }, unit: null, label: "Stop if rash" };
  }
}

export function whatsappText(message: string, senderName: string, url: string): string {
  return `${senderName ? `Hi, this is ${senderName}. ` : ""}Please read this carefully:\n\n${message}\n\nAfter reading, tell me in your own words what you need to do (voice or text, any language is fine):\n${url}`;
}

export function whatsappLink(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}
