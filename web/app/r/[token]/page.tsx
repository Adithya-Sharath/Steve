"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Send } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { CardSkeleton, ErrorState } from "@/components/states";
import { VoiceRecorder } from "@/components/voice-recorder";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const LANGS = [
  { id: "", label: "Auto" },
  { id: "ml", label: "Malayalam" },
  { id: "hi", label: "Hindi" },
  { id: "en", label: "English" },
];

function Confetti() {
  const colors = ["var(--understood)", "var(--primary)", "var(--missing)", "var(--negated)", "var(--wrong)"];
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 top-10 flex justify-center">
      {Array.from({ length: 22 }).map((_, i) => {
        const angle = (i / 22) * Math.PI * 2;
        const d = 90 + (i % 5) * 26;
        return (
          <motion.span
            key={i}
            className="absolute size-2 rounded-sm"
            style={{ background: colors[i % colors.length] }}
            initial={{ x: 0, y: 0, opacity: 1, rotate: 0, scale: 0.6 }}
            animate={{ x: Math.cos(angle) * d, y: Math.sin(angle) * d + 40, opacity: 0, rotate: 200 + i * 20, scale: 1 }}
            transition={{ duration: 1.3, ease: "easeOut", delay: 0.15 }}
          />
        );
      })}
    </div>
  );
}

function Done({ sender, again }: { sender: string; again: () => void }) {
  return (
    <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="relative flex flex-col items-center px-4 py-16 text-center">
      <Confetti />
      <motion.svg viewBox="0 0 52 52" className="size-24 text-understood" initial="hidden" animate="show">
        <motion.circle cx="26" cy="26" r="24" fill="var(--understood-soft)" stroke="currentColor" strokeWidth="2" variants={{ hidden: { pathLength: 0 }, show: { pathLength: 1 } }} transition={{ duration: 0.6 }} />
        <motion.path d="M15 27l8 8 15-17" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" variants={{ hidden: { pathLength: 0 }, show: { pathLength: 1 } }} transition={{ duration: 0.5, delay: 0.45 }} />
      </motion.svg>
      <h1 className="mt-6 font-display text-5xl leading-none">Thank you!</h1>
      <p className="mt-3 max-w-xs text-lg text-muted-foreground">{sender ? `${sender} has your answer.` : "Your answer has been sent."}</p>
      <Button variant="ghost" className="mt-8" onClick={again}>Add something else</Button>
    </motion.div>
  );
}

export default function ReaderPage() {
  const { token } = useParams<{ token: string }>();
  const q = useQuery({ queryKey: ["reader", token], queryFn: () => api.reader(token), retry: false });
  const [text, setText] = useState("");
  const [lang, setLang] = useState("");
  const [done, setDone] = useState(false);

  const send = useMutation({
    mutationFn: (p: { text?: string; audio?: Blob }) => api.sendReply(token, { ...p, lang_hint: lang || undefined }),
    onSuccess: () => {
      setDone(true);
      setText("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (q.isLoading) return <div className="mx-auto max-w-md px-4 py-10"><CardSkeleton lines={4} /></div>;
  if (q.isError || !q.data)
    return <div className="mx-auto max-w-md px-4 py-16"><ErrorState message={(q.error as Error)?.message || "This link is not valid."} onRetry={() => q.refetch()} /></div>;
  const v = q.data;

  return (
    <div className="mx-auto min-h-dvh max-w-md px-4 pb-16 pt-8">
      <AnimatePresence mode="wait">
        {done ? (
          <Done key="done" sender={v.sender_name} again={() => setDone(false)} />
        ) : (
          <motion.div key="form" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-8">
            <header>
              <p className="text-sm text-muted-foreground">Message from</p>
              <p className="font-display text-3xl leading-tight">{v.sender_name || "Someone you know"}</p>
            </header>

            <section className="card-soft p-5" aria-label="The message">
              <p className="text-[17px] leading-relaxed">{v.text}</p>
            </section>

            <section aria-labelledby="prompt">
              <h1 id="prompt" className="font-display text-4xl leading-tight">{v.prompt.title}</h1>
              <p className="mt-2 text-[17px] leading-relaxed text-muted-foreground">{v.prompt.body}</p>
              <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted-foreground" lang="und">
                <span>മലയാളം</span><span>हिन्दी / اردو</span><span>العربية</span><span>Tagalog</span><span>English</span>
              </p>
            </section>

            {v.stt_enabled && (
              <section aria-label="Speak your answer" className="space-y-4">
                <div role="radiogroup" aria-label="Language you will speak" className="flex flex-wrap justify-center gap-1.5">
                  {LANGS.map((l) => (
                    <button key={l.id} role="radio" aria-checked={lang === l.id} onClick={() => setLang(l.id)}
                      className={cn("rounded-full border px-3 py-1 text-sm pressable", lang === l.id ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card")}>
                      {l.label}
                    </button>
                  ))}
                </div>
                <VoiceRecorder busy={send.isPending} onSend={(wav) => send.mutate({ audio: wav })} />
                <p className="flex items-center gap-3 text-sm text-muted-foreground before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">or type</p>
              </section>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (text.trim()) send.mutate({ text });
              }}
              className="space-y-3"
            >
              <label htmlFor="reply" className={v.stt_enabled ? "sr-only" : "block text-sm font-medium"}>Your answer</label>
              <Textarea id="reply" value={text} onChange={(e) => setText(e.target.value)} rows={4} placeholder="Type it however you would say it…" className="text-[17px]" lang="und" autoCapitalize="off" spellCheck={false} />
              <Button type="submit" size="lg" className="h-12 w-full text-base" disabled={!text.trim() || send.isPending}>
                {send.isPending ? <Loader2 className="animate-spin" /> : <Send />} Send my answer
              </Button>
            </form>
            <p className="text-center text-xs text-muted-foreground">
              Only {v.sender_name || "the sender"} sees your answer. Recordings are never saved.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
