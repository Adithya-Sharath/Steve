"use client";

import { Check, Copy, MessageCircle, Send } from "lucide-react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import { toast } from "sonner";
import { SimulateReply } from "@/components/simulate-reply";
import { Button, buttonVariants } from "@/components/ui/button";
import { whatsappLink, whatsappText } from "@/lib/facts";
import { cn } from "@/lib/utils";

/** Post-confirm share sheet: link, QR, prefilled WhatsApp text, and a demo "Simulate reply". */
export function ShareSheet({
  messageId,
  token,
  message,
  senderName,
}: {
  messageId: string;
  token: string;
  message: string;
  senderName: string;
}) {
  const [copied, setCopied] = useState<"link" | "wa" | null>(null);
  // this component only mounts after a click, so reading window here cannot cause a hydration mismatch
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const url = `${origin}/r/${token}`;
  const wa = whatsappText(message, senderName, url);

  const copy = async (what: "link" | "wa") => {
    try {
      await navigator.clipboard.writeText(what === "link" ? url : wa);
      setCopied(what);
      toast.success(what === "link" ? "Link copied" : "WhatsApp message copied");
      setTimeout(() => setCopied(null), 1800);
    } catch {
      toast.error("Copy failed. Select the text and copy it manually.");
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[auto_1fr]">
      <div className="card-soft flex flex-col items-center gap-3 p-6">
        <div className="rounded-2xl bg-white p-3">{origin && <QRCodeSVG value={url} size={176} level="M" />}</div>
        <p className="max-w-[12rem] text-center text-xs text-muted-foreground">
          Scan on a phone. On a laptop, open this site via your LAN address (or deploy) so the phone can reach it.
        </p>
      </div>
      <div className="space-y-4">
        <div className="card-soft p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Reader link</p>
          <p className="mt-1 break-all font-mono text-sm">{url}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => copy("link")}>{copied === "link" ? <Check /> : <Copy />} Copy link</Button>
            <Button variant="outline" onClick={() => copy("wa")}>{copied === "wa" ? <Check /> : <MessageCircle />} Copy WhatsApp message</Button>
            <a href={whatsappLink(wa)} target="_blank" rel="noreferrer" className={cn(buttonVariants({ variant: "outline" }))}>
              <Send /> Open in WhatsApp
            </a>
          </div>
          <pre className="mt-4 max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-muted/60 p-3 text-xs leading-relaxed">{wa}</pre>
        </div>
        <div className="card-soft p-5">
          <p className="font-medium">Waiting for the reply? Simulate one.</p>
          <p className="mb-3 text-sm text-muted-foreground">Handy for demos: posts a reply exactly as the reader page would.</p>
          <SimulateReply token={token} messageText={message} onSent={() => {}} />
        </div>
        <Link href={`/app/m/${messageId}`} className={cn(buttonVariants({ size: "lg" }), "h-11 px-5 text-base")}>
          Open live results
        </Link>
      </div>
    </div>
  );
}
