"use client";

import { useSyncExternalStore } from "react";

/**
 * Operator-only admin key (the server's ADMIN_KEY), kept in this browser's localStorage and sent as `X-Admin-Key`
 * only to flip the GLOBAL LLM switch. Visitors never have one, so they never see that switch (D30).
 * Entered on the unlinked /admin page. It is a secret: it is never put in a URL and never sent anywhere else.
 */
const STORAGE_KEY = "steve_admin_key";
const EVENT = "steve-admin-key";

export function getAdminKey(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setAdminKey(key: string): void {
  try {
    if (key) window.localStorage.setItem(STORAGE_KEY, key);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {}
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

/** Hydration-safe: the server snapshot is "no key", so the toggle never appears in server HTML. */
export function useAdminKey(): string {
  return useSyncExternalStore(subscribe, getAdminKey, () => "");
}
