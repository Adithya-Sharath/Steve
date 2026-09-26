"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useWaking, withWake } from "@/lib/waking";

/** One shared health query: the first page load pings `GET /decode/health` so a sleeping API host starts waking before anything is tapped (D50). */
export function useDecodeHealth() {
  return useQuery({ queryKey: ["decode-health"], queryFn: () => withWake(api.decodeHealth), retry: false, staleTime: 60_000 });
}

export function WarmUp() {
  useDecodeHealth();
  return null;
}

/** Shown app-wide while any request is waiting for a sleeping server. */
export function WakingBanner() {
  const waking = useWaking();
  if (!waking) return null;
  return (
    <div role="status" aria-live="polite" data-testid="waking" className="sticky top-14 z-30 border-b border-missing/40 bg-missing-soft px-4 py-2 text-center text-sm text-missing-ink">
      <Loader2 className="mr-2 inline size-4 animate-spin motion-reduce:animate-none" aria-hidden />
      Waking up the server… this can take up to a minute the first time.
    </div>
  );
}
