"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(cb: () => void) {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

/**
 * Hydration-safe `prefers-reduced-motion`. framer-motion's own hook reads the media query synchronously on the
 * client, so anything that BRANCHES ITS RENDER on it produces different HTML on server and client (React error #418).
 * With useSyncExternalStore the server snapshot (false) is used for hydration, then it re-renders with the real value.
 */
export function useReducedMotionSafe(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}
