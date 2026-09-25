"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { LANG_LABEL } from "@/lib/status";

/** Demo helper: posts a reply through the same endpoint the reader page uses. Presets come from data/scenarios.json. */
export function SimulateReply({ token, messageText, onSent }: { token: string; messageText: string; onSent?: () => void }) {
  const sc = useQuery({ queryKey: ["scenarios"], queryFn: api.scenarios });
  const [text, setText] = useState("");
  const scenario = sc.data?.find((s) => s.text.trim() === messageText.trim());
  const send = useMutation({
    mutationFn: (t: string) => api.sendReply(token, { text: t }),
    onSuccess: () => {
      toast.success("Reply sent");
      setText("");
      onSent?.();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <div className="space-y-3">
      {scenario && (
        <div className="flex flex-wrap gap-2" aria-label="Preset replies">
          {scenario.presets.map((p) => (
            <Button key={p.id} variant="outline" size="sm" disabled={send.isPending} onClick={() => send.mutate(p.text)} title={p.text}>
              <Play /> {p.label} · <span className="text-muted-foreground">{LANG_LABEL[p.lang_mix] ?? p.lang_mix}</span>
            </Button>
          ))}
        </div>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) send.mutate(text);
        }}
        className="flex flex-col gap-2 sm:flex-row"
      >
        <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} placeholder="…or type any reply, e.g. randu gulika, food kazhinju" className="font-mono text-sm" aria-label="Reply to simulate" />
        <Button type="submit" disabled={!text.trim() || send.isPending} className="sm:self-end">
          {send.isPending ? <Loader2 className="animate-spin" /> : null} Send
        </Button>
      </form>
    </div>
  );
}
