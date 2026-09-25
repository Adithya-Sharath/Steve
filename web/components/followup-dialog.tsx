"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { CardSkeleton, ErrorState } from "@/components/states";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { whatsappLink } from "@/lib/facts";
import { STATUS_META } from "@/lib/status";
import { cn } from "@/lib/utils";

/** Re-explanation draft covering ONLY the failed facts. Template-based (nothing is translated), editable, copyable. */
export function FollowupDialog({ messageId, open, onOpenChange, readerUrl }: { messageId: string; open: boolean; onOpenChange: (o: boolean) => void; readerUrl?: string | null }) {
  const q = useQuery({ queryKey: ["followup", messageId, open], queryFn: () => api.followup(messageId), enabled: open, staleTime: 0 });
  const [edited, setEdited] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const base = q.data ? (readerUrl && q.data.failed.length ? `${q.data.draft}\n${readerUrl}` : q.data.draft) : "";
  const draft = edited ?? base;
  const setDraft = setEdited;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Draft follow-up</DialogTitle>
          <DialogDescription>Covers only what didn&apos;t land, in the sender&apos;s own language. Edit before sending.</DialogDescription>
        </DialogHeader>
        {q.isError ? (
          <ErrorState message={(q.error as Error).message} onRetry={() => q.refetch()} />
        ) : !q.data ? (
          <CardSkeleton lines={3} />
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5">
              {q.data.failed.map((f) => {
                const m = STATUS_META[f.status];
                return (
                  <span key={f.fact_id} className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium", m.chip)}>
                    <m.icon className="size-3" aria-hidden /> {f.label}
                  </span>
                );
              })}
              {!q.data.failed.length && <span className="text-sm text-understood-ink">Everything checked out. Nothing to re-explain.</span>}
            </div>
            <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={8} aria-label="Follow-up draft" className="text-[15px]" />
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(draft);
                    setCopied(true);
                    toast.success("Copied");
                    setTimeout(() => setCopied(false), 1500);
                  } catch {
                    toast.error("Copy failed");
                  }
                }}
              >
                {copied ? <Check /> : <Copy />} Copy
              </Button>
              <a href={whatsappLink(draft)} target="_blank" rel="noreferrer" className={cn(buttonVariants({ variant: "outline" }))}>
                <Send /> WhatsApp
              </a>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
