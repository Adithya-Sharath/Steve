"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Loader2, Play, RefreshCw, Smartphone } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { CardSkeleton, ErrorState } from "@/components/states";
import { Button, buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { CONTEXTS } from "@/lib/facts";
import { LANG_LABEL } from "@/lib/status";
import { cn } from "@/lib/utils";

/** Demo mode: pre-seeds the four scenarios so a video can be recorded reliably even if speech-to-text is slow. */
export default function DemoPage() {
  const qc = useQueryClient();
  const sc = useQuery({ queryKey: ["scenarios"], queryFn: api.scenarios });
  const seed = useMutation({
    mutationFn: api.seed,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages"] }),
    onError: (e: Error) => toast.error(e.message),
  });
  const started = useRef(false);
  useEffect(() => {
    if (!started.current) {
      started.current = true;
      seed.mutate();
    }
  }, [seed]);

  const tokens = new Map((seed.data?.seeded ?? []).map((s) => [s.scenario, s]));
  const send = useMutation({
    mutationFn: ({ token, text }: { token: string; text: string }) => api.sendReply(token, { text }),
    onSuccess: () => toast.success("Reply sent. Open the sender view to see it resolve."),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">Demo mode</p>
      <h1 className="mt-1 font-display text-5xl leading-[1.02] sm:text-6xl">Four real-life messages, ready to go.</h1>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
        Everything is pre-seeded. Send a preset reply (no microphone, no keys) and watch the sender dashboard resolve fact by fact. Or use the reader link on a phone and speak.
      </p>
      <div className="mt-6 flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => seed.mutate()} disabled={seed.isPending}>
          {seed.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} Reset demo data
        </Button>
        <Link href="/app" className={cn(buttonVariants({ variant: "outline" }))}>Sender dashboard</Link>
        <Link href="/app/new" className={cn(buttonVariants())}>Compose your own</Link>
      </div>

      <div className="mt-10 grid gap-5">
        {sc.isLoading && <CardSkeleton lines={4} />}
        {sc.isError && <ErrorState message={(sc.error as Error).message} onRetry={() => sc.refetch()} />}
        {seed.isError && <ErrorState message="Could not seed the demo data. Is the API running?" onRetry={() => seed.mutate()} />}
        {sc.data?.map((s) => {
          const seeded = tokens.get(s.id);
          return (
            <article key={s.id} className="card-soft p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">{CONTEXTS.find((c) => c.id === s.context)?.emoji} {s.sender_name}</p>
                  <h2 className="font-display text-3xl">{s.title}</h2>
                </div>
                {seeded && (
                  <div className="flex flex-wrap gap-2">
                    <Link href={`/app/m/${seeded.message_id}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>Sender view <ExternalLink /></Link>
                    <Link href={`/r/${seeded.reader_token}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}><Smartphone /> Reader page</Link>
                  </div>
                )}
              </div>
              <p className="mt-2 leading-relaxed">{s.text}</p>
              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                {s.presets.map((p) => (
                  <button
                    key={p.id}
                    disabled={!seeded || send.isPending}
                    onClick={() => seeded && send.mutate({ token: seeded.reader_token, text: p.text })}
                    className="group rounded-2xl border border-border bg-background p-3 text-left transition-colors hover:border-primary/50 hover:bg-teal-soft/50 disabled:opacity-50"
                  >
                    <span className="flex items-center justify-between text-xs text-muted-foreground">
                      {LANG_LABEL[p.lang_mix] ?? p.lang_mix}
                      <Play className="size-3.5 text-primary" aria-hidden />
                    </span>
                    <span className="mt-1 block text-sm font-medium">{p.label}</span>
                    <span className="mt-1.5 line-clamp-2 block font-mono text-xs text-muted-foreground">{p.text}</span>
                  </button>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
