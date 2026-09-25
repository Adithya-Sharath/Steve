"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import type { Reply } from "@/lib/types";

/** Server-Sent Events: pushes new replies (with per-fact results) to the sender dashboard live. */
export function useMessageStream(messageId: string | undefined, onReply: (r: Reply) => void) {
  const cb = useRef(onReply);
  useEffect(() => {
    cb.current = onReply;
  });
  useEffect(() => {
    if (!messageId) return;
    const es = new EventSource(api.streamUrl(messageId));
    es.addEventListener("reply", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as { reply: Reply };
        cb.current(data.reply);
      } catch {}
    });
    return () => es.close();
  }, [messageId]);
}
