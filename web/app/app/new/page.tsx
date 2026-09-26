"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Loader2, Wand2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { FactEditor } from "@/components/fact-editor";
import { LlmOffBadge } from "@/components/llm-toggle";
import { ShareSheet } from "@/components/share-sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { CONTEXTS } from "@/lib/facts";
import type { Context, Fact } from "@/lib/types";
import { cn } from "@/lib/utils";

type Stage = "write" | "facts" | "share";

export default function Composer() {
  const [stage, setStage] = useState<Stage>("write");
  const [text, setText] = useState("");
  const [sender, setSender] = useState("");
  const [context, setContext] = useState<Context>("pharmacy");
  const [messageId, setMessageId] = useState("");
  const [facts, setFacts] = useState<Fact[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [extractor, setExtractor] = useState<string>("");
  const [token, setToken] = useState("");

  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: api.scenarios });

  const find = useMutation({
    mutationFn: () => api.createMessage({ text, sender_name: sender, context }),
    onSuccess: (r) => {
      setMessageId(r.message_id);
      setFacts(r.suggested_facts);
      setNote(r.note);
      setExtractor(r.extractor);
      setStage("facts");
      if (!r.suggested_facts.length) toast("No facts found automatically. Add them by hand below.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const confirm = useMutation({
    mutationFn: () => api.confirm(messageId, facts),
    onSuccess: (r) => {
      setToken(r.reader_token);
      setStage("share");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const steps: { id: Stage; label: string }[] = [
    { id: "write", label: "Write" },
    { id: "facts", label: "Confirm facts" },
    { id: "share", label: "Share" },
  ];
  const stageIdx = steps.findIndex((s) => s.id === stage);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <Link href="/app" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Dashboard
      </Link>
      <h1 className="mt-2 font-display text-5xl leading-none">New message</h1>

      <ol className="mt-6 flex items-center gap-2 text-sm" aria-label="Progress">
        {steps.map((s, i) => (
          <li key={s.id} className="flex items-center gap-2" aria-current={i === stageIdx ? "step" : undefined}>
            <span className={cn("grid size-6 place-items-center rounded-full text-xs font-medium", i <= stageIdx ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{i + 1}</span>
            <span className={i === stageIdx ? "font-medium" : "text-muted-foreground"}>{s.label}</span>
            {i < steps.length - 1 && <span className="mx-1 h-px w-8 bg-border" aria-hidden />}
          </li>
        ))}
      </ol>

      <div className="mt-8">
        <AnimatePresence mode="wait">
          {stage === "write" && (
            <motion.form
              key="write"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              onSubmit={(e) => {
                e.preventDefault();
                if (text.trim()) find.mutate();
              }}
              className="space-y-6"
            >
              <fieldset>
                <legend className="mb-2 text-sm font-medium">What kind of message?</legend>
                <div className="flex flex-wrap gap-2">
                  {CONTEXTS.map((c) => (
                    <label key={c.id} className={cn("cursor-pointer rounded-full border px-3.5 py-1.5 text-sm pressable has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50", context === c.id ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted")}>
                      <input type="radio" name="context" value={c.id} checked={context === c.id} onChange={() => setContext(c.id)} className="sr-only" />
                      <span aria-hidden>{c.emoji}</span> {c.label}
                    </label>
                  ))}
                </div>
              </fieldset>
              <div>
                <label htmlFor="sender" className="mb-1.5 block text-sm font-medium">Your name (shown to the reader)</label>
                <Input id="sender" value={sender} onChange={(e) => setSender(e.target.value)} placeholder="e.g. Priya, Al Noor Pharmacy" className="max-w-sm" />
              </div>
              <div>
                <label htmlFor="msg" className="mb-1.5 block text-sm font-medium">The important message</label>
                <Textarea id="msg" value={text} onChange={(e) => setText(e.target.value)} rows={5} placeholder="Take 2 tablets after food, twice a day, for 5 days. Stop taking them and call us if you get a rash." className="text-base" required />
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>Try an example:</span>
                  {(scenarios.data ?? []).map((s) => (
                    <button key={s.id} type="button" onClick={() => { setText(s.text); setContext(s.context); setSender(s.sender_name); }} className="rounded-full border border-border bg-card px-2.5 py-1 hover:bg-muted">
                      {s.title.split(" · ")[0]}
                    </button>
                  ))}
                </div>
              </div>
              <Button type="submit" size="lg" className="h-11 px-5 text-base" disabled={!text.trim() || find.isPending}>
                {find.isPending ? <Loader2 className="animate-spin" /> : <Wand2 />} Find key facts
              </Button>
            </motion.form>
          )}

          {stage === "facts" && (
            <motion.div key="facts" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
              <div className="card-soft mb-6 p-4">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Your message</p>
                <p className="mt-1 leading-relaxed">{text}</p>
              </div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="font-display text-3xl">Check these facts?</h2>
                  <p className="text-sm text-muted-foreground">
                    Found by {extractor === "llm" ? "the optional LLM helper" : "built-in rules (no LLM)"}. Edit, add or remove: you decide what counts as understood.
                  </p>
                </div>
                <LlmOffBadge />
              </div>
              {note && <p className="mb-3 rounded-xl border border-missing/40 bg-missing-soft px-3 py-2 text-sm text-missing-ink">{note}</p>}
              <FactEditor facts={facts} onChange={setFacts} />
              <div className="mt-8 flex flex-wrap gap-3">
                <Button variant="outline" onClick={() => setStage("write")}>Back</Button>
                <Button size="lg" className="h-11 px-5 text-base" disabled={!facts.length || confirm.isPending} onClick={() => confirm.mutate()}>
                  {confirm.isPending && <Loader2 className="animate-spin" />} Confirm &amp; get link
                </Button>
              </div>
            </motion.div>
          )}

          {stage === "share" && (
            <motion.div key="share" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
              <h2 className="mb-1 font-display text-3xl">Ready to send</h2>
              <p className="mb-6 text-sm text-muted-foreground">The reader opens the link, explains it back, and never sees a score.</p>
              <ShareSheet messageId={messageId} token={token} message={text} senderName={sender} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
