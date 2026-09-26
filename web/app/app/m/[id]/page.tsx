"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { ArrowLeft, ChevronDown, Copy, Mic, PenLine, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { FactCard } from "@/components/fact-card";
import { FollowupDialog } from "@/components/followup-dialog";
import { LlmOffBadge } from "@/components/llm-toggle";
import { SimulateReply } from "@/components/simulate-reply";
import { StatusRing } from "@/components/status-ring";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/states";
import { Transcript } from "@/components/transcript";
import { Button } from "@/components/ui/button";
import { useMessageStream } from "@/hooks/use-message-stream";
import { api } from "@/lib/api";
import { STATUS_ORDER } from "@/lib/status";
import { toCodePoints, type Highlight } from "@/lib/spans";
import type { ConditionValue, MessageOut, Status } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Find each fact in the ORIGINAL message (best effort, by text) and return code-point highlights. */
function messageHighlights(m: MessageOut, statusOf: (id: string) => Status | undefined): Highlight[] {
  const text = m.text;
  const lower = text.toLowerCase();
  const out: Highlight[] = [];
  for (const f of m.facts) {
    const needles =
      f.type === "condition"
        ? [(f.value as ConditionValue).text, (f.value as ConditionValue).trigger]
        : [f.label, f.label.replace(/^by |^at /i, "")];
    for (const n of needles) {
      const i = n ? lower.indexOf(n.toLowerCase()) : -1;
      if (i >= 0) {
        const start = toCodePoints(text.slice(0, i)).length;
        out.push({ id: f.id, span: { start, end: start + toCodePoints(n).length, text: n }, status: statusOf(f.id) });
        break;
      }
    }
  }
  return out;
}

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["message", id], queryFn: () => api.getMessage(id), refetchInterval: 15000 });
  const [active, setActive] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [followOpen, setFollowOpen] = useState(false);
  const [showSim, setShowSim] = useState(false);

  useMessageStream(id, (reply) => {
    qc.invalidateQueries({ queryKey: ["message", id] });
    qc.invalidateQueries({ queryKey: ["messages"] });
    setSelected(reply.id);
    toast("New reply just came in", { description: reply.text.slice(0, 80) });
  });

  const m = q.data;
  const replyList = useMemo(() => m?.replies ?? [], [m]);
  const current = replyList.find((r) => r.id === selected) ?? replyList[replyList.length - 1];

  const copied = !!current && current.results.length > 0 && current.results.every((r) => r.flags?.includes("copied"));
  const resultMap = useMemo(() => new Map((current?.results ?? []).map((r) => [r.fact_id, r])), [current]);
  const latestStatus = useMemo(() => new Map((m?.latest ?? []).map((l) => [l.fact_id, replyList.length ? l.status : undefined])), [m, replyList]);
  const msgHighlights = useMemo(() => (m ? messageHighlights(m, (fid) => latestStatus.get(fid)) : []), [m, latestStatus]);
  const replyHighlights: Highlight[] = useMemo(
    () => (current?.results ?? []).flatMap((r) => r.evidence.map((span) => ({ id: r.fact_id, span, status: r.status }))),
    [current],
  );
  const sortedFacts = useMemo(() => {
    if (!m) return [];
    const rank = (fid: string) => {
      const r = resultMap.get(fid);
      return r ? STATUS_ORDER.indexOf(r.status) : STATUS_ORDER.length + 1;
    };
    return [...m.facts].sort((a, b) => rank(a.id) - rank(b.id));
  }, [m, resultMap]);

  if (q.isLoading)
    return <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-[1fr_1.3fr]"><CardSkeleton lines={6} /><CardSkeleton lines={6} /></div>;
  if (q.isError || !m)
    return <div className="px-4 py-16"><ErrorState message={(q.error as Error)?.message ?? "Message not found"} onRetry={() => q.refetch()} /></div>;

  const failedCount = m.aggregate.total - m.aggregate.understood;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <Link href="/app" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Dashboard
      </Link>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          {replyList.length > 0 && <StatusRing aggregate={m.aggregate} size={72} />}
          <div>
            <h1 className="font-display text-4xl leading-none">
              {replyList.length === 0 ? "Waiting for a reply" : failedCount === 0 ? "Everything landed" : `${failedCount} thing${failedCount === 1 ? "" : "s"} didn't land`}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {m.sender_name || "You"} · {m.aggregate.total} facts · {replyList.length} repl{replyList.length === 1 ? "y" : "ies"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <LlmOffBadge />
          <Button onClick={() => setFollowOpen(true)} disabled={replyList.length === 0} variant={failedCount > 0 ? "default" : "outline"}>
            <PenLine /> Draft follow-up
          </Button>
        </div>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_1.35fr]">
        {/* left: the message with facts highlighted */}
        <section aria-labelledby="orig" className="space-y-6 lg:sticky lg:top-20 lg:self-start">
          <div className="card-soft p-5">
            <h2 id="orig" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Your message</h2>
            <Transcript text={m.text} highlights={msgHighlights} activeId={active} onHover={setActive} className="mt-2 font-sans text-base leading-8" />
          </div>
          <div className="card-soft p-4">
            <button className="flex w-full items-center justify-between text-left text-sm font-medium" aria-expanded={showSim} onClick={() => setShowSim((v) => !v)}>
              <span className="flex items-center gap-2"><Send className="size-4 text-primary" /> Simulate a reply (demo)</span>
              <ChevronDown className={cn("size-4 transition-transform", showSim && "rotate-180")} />
            </button>
            {showSim && m.reader_token && (
              <div className="mt-3"><SimulateReply token={m.reader_token} messageText={m.text} /></div>
            )}
          </div>
        </section>

        {/* right: replies + facts */}
        <section aria-labelledby="replies" className="space-y-5">
          <h2 id="replies" className="sr-only">Replies and results</h2>
          {replyList.length > 1 && (
            <div role="tablist" aria-label="Replies" className="flex flex-wrap gap-2">
              {replyList.map((r, i) => (
                <button key={r.id} role="tab" aria-selected={r.id === current?.id} onClick={() => setSelected(r.id)}
                  className={cn("rounded-full border px-3 py-1 text-sm", r.id === current?.id ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted")}>
                  Reply {i + 1}
                </button>
              ))}
            </div>
          )}

          {copied && current && (
            <motion.div
              role="status"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 rounded-2xl border border-unclear/50 bg-unclear-soft p-4 text-unclear-ink"
            >
              <Copy className="mt-0.5 size-5 shrink-0" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="font-medium">This reply looks copied from your message</p>
                <p className="mt-0.5 text-sm">
                  Pasting the message back doesn&apos;t show understanding, so every fact is marked unclear. Ask them to say it in their own words.
                </p>
              </div>
              <Button size="sm" variant="outline" onClick={() => setFollowOpen(true)}>
                Draft follow-up
              </Button>
            </motion.div>
          )}
          {current ? (
            <motion.div key={current.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-soft p-5">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {current.source === "voice" ? <Mic className="size-3.5" /> : <PenLine className="size-3.5" />}
                The reader&apos;s words, verbatim
                <span className="ml-auto normal-case tracking-normal">{new Date(current.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
              </div>
              <Transcript text={current.text} highlights={replyHighlights} activeId={active} onHover={setActive} />
            </motion.div>
          ) : (
            <EmptyState
              title="No reply yet"
              body="Share the link with the reader. Results appear here live, fact by fact. Or simulate a reply on the left."
              className="max-w-none"
            />
          )}

          <LayoutGroup>
            <ul className="grid gap-3" aria-live="polite">
              <AnimatePresence initial={false}>
                {sortedFacts.map((f, i) => (
                  <FactCard key={f.id} order={i} fact={f} result={resultMap.get(f.id)} pending={!current} active={active === f.id} onHover={setActive} />
                ))}
              </AnimatePresence>
            </ul>
          </LayoutGroup>
        </section>
      </div>

      <FollowupDialog messageId={m.id} open={followOpen} onOpenChange={setFollowOpen} readerUrl={null} />
    </div>
  );
}
