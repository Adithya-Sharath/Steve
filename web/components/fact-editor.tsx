"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ACTIONS, DOSE_UNITS, DURATION_UNITS, TIMING_TAGS, autoLabel, blankFact } from "@/lib/facts";
import { FACT_ICON, FACT_TYPE_LABEL } from "@/lib/status";
import type { ConditionValue, Fact, FactType } from "@/lib/types";
import { cn } from "@/lib/utils";

const selectCls =
  "h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50";

function ValueEditor({ fact, onChange }: { fact: Fact; onChange: (patch: Partial<Fact>) => void }) {
  const v = fact.value;
  const num = (x: string) => (x === "" ? 0 : Number(x));
  switch (fact.type) {
    case "dose":
    case "duration":
    case "amount": {
      const units = fact.type === "dose" ? DOSE_UNITS : fact.type === "duration" ? DURATION_UNITS : null;
      return (
        <div className="flex items-center gap-2">
          <Input type="number" min={0} step="any" value={Number(v)} onChange={(e) => onChange({ value: num(e.target.value) })} className="w-24" aria-label="Value" />
          {units ? (
            <select className={selectCls} value={fact.unit ?? units[0]} onChange={(e) => onChange({ unit: e.target.value })} aria-label="Unit">
              {units.map((u) => <option key={u}>{u}</option>)}
            </select>
          ) : (
            <Input value={fact.unit ?? ""} onChange={(e) => onChange({ unit: e.target.value.toUpperCase() })} className="w-24" aria-label="Currency" placeholder="AED" />
          )}
        </div>
      );
    }
    case "frequency":
      return (
        <div className="flex items-center gap-2">
          <Input type="number" min={0} step="any" value={Number(v)} onChange={(e) => onChange({ value: num(e.target.value) })} className="w-24" aria-label="Times per day" />
          <span className="text-sm text-muted-foreground">times a day</span>
        </div>
      );
    case "timing": {
      const tags = new Set(Array.isArray(v) ? v : [String(v)]);
      return (
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="When">
          {TIMING_TAGS.map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={tags.has(t)}
              onClick={() => {
                const next = new Set(tags);
                if (next.has(t)) next.delete(t);
                else next.add(t);
                const arr = [...next];
                onChange({ value: arr.length === 1 ? arr[0] : arr });
              }}
              className={cn("rounded-full border px-2.5 py-1 text-xs transition-colors", tags.has(t) ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted")}
            >
              {t.replace("_", " ")}
            </button>
          ))}
        </div>
      );
    }
    case "date":
      return <Input value={String(v)} onChange={(e) => onChange({ value: e.target.value.toLowerCase() })} className="w-48" aria-label="Weekday, time HH:MM or ISO date" placeholder="thursday · 12:30 · 2026-03-15" />;
    case "condition": {
      const c = v as ConditionValue;
      const set = (p: Partial<ConditionValue>) => onChange({ value: { ...c, ...p } });
      return (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">if</span>
          <Input value={c.trigger} onChange={(e) => set({ trigger: e.target.value })} className="w-32" aria-label="Trigger (e.g. rash)" />
          <span className="text-sm text-muted-foreground">then</span>
          <select className={selectCls} value={c.action} onChange={(e) => set({ action: e.target.value as ConditionValue["action"] })} aria-label="Action">
            {ACTIONS.map((a) => <option key={a} value={a}>{a.replace("_", " ")}</option>)}
          </select>
        </div>
      );
    }
  }
}

/** Editable fact chips. Works with the LLM off: add/remove/edit everything by hand. */
export function FactEditor({ facts, onChange }: { facts: Fact[]; onChange: (f: Fact[]) => void }) {
  const [auto, setAuto] = useState<Set<string>>(() => new Set(facts.map((f) => f.id)));
  const [adding, setAdding] = useState<FactType>("dose");

  const patch = (id: string, p: Partial<Fact>) =>
    onChange(
      facts.map((f) => {
        if (f.id !== id) return f;
        const next = { ...f, ...p };
        if (auto.has(id) && !("label" in p)) next.label = autoLabel(next);
        return next;
      }),
    );

  return (
    <div>
      <ul className="grid gap-3" aria-label="Key facts to check">
        <AnimatePresence initial>
          {facts.map((f, i) => {
            const Icon = FACT_ICON[f.type];
            return (
              <motion.li
                key={f.id}
                layout
                initial={{ opacity: 0, y: 14, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ type: "spring", stiffness: 380, damping: 30, delay: i * 0.05 }}
                className="card-soft list-none p-4"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-1 grid size-9 shrink-0 place-items-center rounded-xl bg-teal-soft text-primary">
                    <Icon className="size-[18px]" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{FACT_TYPE_LABEL[f.type]}</span>
                      <Input
                        value={f.label}
                        onChange={(e) => {
                          setAuto((s) => { const n = new Set(s); n.delete(f.id); return n; });
                          patch(f.id, { label: e.target.value });
                        }}
                        className="min-w-40 flex-1 font-medium"
                        aria-label="Label shown on the results page"
                      />
                    </div>
                    <ValueEditor fact={f} onChange={(p) => patch(f.id, p)} />
                  </div>
                  <div className="flex flex-col items-end gap-3">
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      Critical
                      <Switch size="sm" checked={f.critical} onCheckedChange={(c) => patch(f.id, { critical: Boolean(c) })} aria-label={`Mark ${f.label} as critical`} />
                    </label>
                    <button
                      type="button"
                      onClick={() => onChange(facts.filter((x) => x.id !== f.id))}
                      className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-wrong-soft hover:text-wrong-ink"
                      aria-label={`Remove ${f.label}`}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                </div>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <select className={cn(selectCls, "h-9")} value={adding} onChange={(e) => setAdding(e.target.value as FactType)} aria-label="Type of fact to add">
          {(Object.keys(FACT_TYPE_LABEL) as FactType[]).map((t) => <option key={t} value={t}>{FACT_TYPE_LABEL[t]}</option>)}
        </select>
        <button
          type="button"
          onClick={() => {
            const f = blankFact(adding, facts);
            setAuto((s) => new Set(s).add(f.id));
            onChange([...facts, f]);
          }}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-dashed border-primary/50 px-3 text-sm text-primary transition-colors hover:bg-teal-soft"
        >
          <Plus className="size-4" aria-hidden /> Add a fact
        </button>
      </div>
    </div>
  );
}
