/**
 * Cold-start handling (D50). A free API host sleeps when idle and needs up to a minute to wake. `withWake` runs a request and, when the server does not answer
 * (network error, 502/503/504) or is slow to answer, tells the whole app to show "Waking up the server..." and retries with backoff for up to `maxMs` (60 s by default).
 * Only requests that are safe to repeat go through it: a request that failed to connect was never processed.
 */
import { useSyncExternalStore } from "react";

let active = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => listeners.delete(cb);
};

export function useWaking(): boolean {
  return useSyncExternalStore(subscribe, () => active > 0, () => false);
}

/** Is this the kind of failure a sleeping server produces? (status 0 = the request never got an answer) */
export function isWakeError(e: unknown): boolean {
  const s = (e as { status?: number } | null)?.status;
  return typeof s === "number" && (s === 0 || s === 502 || s === 503 || s === 504);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface WakeOptions {
  maxMs?: number;
  /** show the banner if the first attempt takes longer than this (a sleeping server often just hangs) */
  slowMs?: number;
  firstDelayMs?: number;
}

export async function withWake<T>(fn: () => Promise<T>, opts: WakeOptions = {}): Promise<T> {
  const { maxMs = 60_000, slowMs = 4_000, firstDelayMs = 1_500 } = opts;
  const start = Date.now();
  let delay = firstDelayMs;
  let showing = false;
  const show = (on: boolean) => {
    if (on === showing) return;
    showing = on;
    active += on ? 1 : -1;
    emit();
  };
  const slow = setTimeout(() => show(true), slowMs);
  try {
    for (;;) {
      try {
        return await fn();
      } catch (e) {
        if (!isWakeError(e) || Date.now() - start + delay > maxMs) throw e;
        show(true);
        await sleep(delay);
        delay = Math.min(Math.round(delay * 1.6), 8_000);
      }
    }
  } finally {
    clearTimeout(slow);
    show(false);
  }
}
