"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { Loader2, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { StatusRing } from "@/components/status-ring";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/states";
import { Button, buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { CONTEXTS } from "@/lib/facts";
import { STATUS_META, STATUS_ORDER } from "@/lib/status";
import type { MessageSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

type Filter = "all" | "attention" | "waiting" | "done";
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "attention", label: "Needs attention" },
  { id: "waiting", label: "Waiting for reply" },
  { id: "done", label: "All understood" },
];

const kindOf = (m: MessageSummary): Filter => {
  if (m.reply_count === 0) return "waiting";
  return m.aggregate.understood === m.aggregate.total ? "done" : "attention";
};

function timeAgo(iso: string) {
  const s = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export default function Dashboard() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["messages"], queryFn: api.listMessages, refetchInterval: 8000 });
  const [filter, setFilter] = useState<Filter>("all");
  const seed = useMutation({
    mutationFn: api.seed,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages"] });
      toast.success("Demo messages loaded");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const rows = useMemo(() => (q.data ?? []).filter((m) => filter === "all" || kindOf(m) === filter), [q.data, filter]);
  const counts = useMemo(() => {
    const c: Record<Filter, number> = { all: 0, attention: 0, waiting: 0, done: 0 };
    (q.data ?? []).forEach((m) => { c.all++; c[kindOf(m)]++; });
    return c;
  }, [q.data]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">Sender dashboard</p>
          <h1 className="mt-1 font-display text-5xl leading-none">Did it land?</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => seed.mutate()} disabled={seed.isPending}>
            {seed.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />} Load demo data
          </Button>
          <Link href="/app/new" className={cn(buttonVariants())}>
            <Plus /> New message
          </Link>
        </div>
      </div>

      <div role="tablist" aria-label="Filter messages" className="mt-8 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            role="tab"
            aria-selected={filter === f.id}
            onClick={() => setFilter(f.id)}
            className={cn(
              "rounded-full border px-3.5 py-1.5 text-sm pressable",
              filter === f.id ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted",
            )}
          >
            {f.label} <span className="ml-1 tabular-nums opacity-70">{counts[f.id]}</span>
          </button>
        ))}
      </div>

      <div className="mt-6">
        {q.isLoading ? (
          <div className="grid gap-4 md:grid-cols-2">{[0, 1, 2, 3].map((i) => <CardSkeleton key={i} />)}</div>
        ) : q.isError ? (
          <ErrorState message={(q.error as Error).message} onRetry={() => q.refetch()} />
        ) : q.data!.length === 0 ? (
          <EmptyState
            title="No messages yet"
            body="Send your first important message and see which facts landed. Or load four ready-made UAE scenarios."
            action={
              <>
                <Button onClick={() => seed.mutate()} disabled={seed.isPending}>Load demo data</Button>
                <Link href="/app/new" className={cn(buttonVariants({ variant: "outline" }))}>Write a message</Link>
              </>
            }
          />
        ) : rows.length === 0 ? (
          <EmptyState title="Nothing here" body="No messages match this filter." />
        ) : (
          <LayoutGroup>
            <ul className="grid gap-4 md:grid-cols-2">
              <AnimatePresence>
                {rows.map((m, i) => (
                  <motion.li
                    key={m.id}
                    layout
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ delay: Math.min(i, 6) * 0.05, type: "spring", stiffness: 320, damping: 30 }}
                    className="list-none"
                  >
                    <Link href={`/app/m/${m.id}`} className="card-soft group block h-full p-5 transition-transform hover:-translate-y-0.5">
                      <div className="flex gap-4">
                        {m.reply_count > 0 ? (
                          <StatusRing aggregate={m.aggregate} />
                        ) : (
                          <div className="grid size-16 shrink-0 place-items-center rounded-full border border-dashed border-border text-[11px] text-muted-foreground" aria-label="No reply yet">
                            waiting
                          </div>
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>{CONTEXTS.find((c) => c.id === m.context)?.emoji}</span>
                            <span className="truncate">{m.sender_name || "You"}</span>
                            <span aria-hidden>·</span>
                            <span>{timeAgo(m.created_at)}</span>
                            {m.demo && <span className="rounded bg-teal-soft px-1.5 py-0.5 text-[10px] font-medium text-primary">DEMO</span>}
                          </div>
                          <p className="mt-1 line-clamp-2 text-[15px] leading-snug">{m.text}</p>
                        </div>
                      </div>
                      <div className="mt-4 flex flex-wrap items-center gap-1.5 text-xs">
                        {m.reply_count === 0 ? (
                          <span className="text-muted-foreground">{m.fact_count} facts to check</span>
                        ) : (
                          STATUS_ORDER.filter((s) => m.aggregate[s] > 0).map((s) => {
                            const meta = STATUS_META[s];
                            const Icon = meta.icon;
                            return (
                              <span key={s} className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium", meta.chip)}>
                                <Icon className="size-3" aria-hidden /> {m.aggregate[s]} {meta.label.toLowerCase()}
                              </span>
                            );
                          })
                        )}
                        <span className="ml-auto text-muted-foreground">{m.reply_count} repl{m.reply_count === 1 ? "y" : "ies"}</span>
                      </div>
                    </Link>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          </LayoutGroup>
        )}
      </div>
    </div>
  );
}
