/**
 * Decode identity and choices, kept ONLY in this browser (D45).
 *  - `steve_worker_key`: a random device key `wk_...` sent as `X-Worker-Key`. A capability, not a password; the server uses only its hash and stores nothing.
 *  - `steve_lang`: the language the worker wants replies in.  `steve_accent`: the optional accent hint.
 * Nothing the worker says or reads is ever stored here.
 */
import { useSyncExternalStore } from "react";
import type { AccentHint, ReplyLanguage } from "./types";

const KEY = "steve_worker_key";
const LANG = "steve_lang";
const ACCENT = "steve_accent";
const KEY_PATTERN = /^wk_[A-Za-z0-9_-]{24,128}$/;
const LANGS: ReplyLanguage[] = ["en", "ml", "hi", "ur", "tl", "bn"];
const ACCENTS: AccentHint[] = ["ar", "hi", "ml", "tl"];
let memoryKey: string | null = null;
const mem: Record<string, string | null> = {};
const listeners = new Set<() => void>();

function read(name: string): string | null {
  try {
    return window.localStorage.getItem(name);
  } catch {
    return mem[name] ?? null;
  }
}
function write(name: string, value: string | null) {
  mem[name] = value;
  try {
    if (value === null) window.localStorage.removeItem(name);
    else window.localStorage.setItem(name, value);
  } catch {}
  listeners.forEach((l) => l());
}
function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

function generate(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return `wk_${btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")}`;
}

export function getWorkerKey(): string {
  if (typeof window === "undefined") return "";
  if (memoryKey) return memoryKey;
  const existing = read(KEY);
  if (existing && KEY_PATTERN.test(existing)) return (memoryKey = existing);
  const fresh = generate();
  write(KEY, fresh);
  return (memoryKey = fresh);
}

export function getLanguage(): ReplyLanguage | null {
  const v = typeof window === "undefined" ? null : read(LANG);
  return v && (LANGS as string[]).includes(v) ? (v as ReplyLanguage) : null;
}
export function setLanguage(l: ReplyLanguage) {
  write(LANG, l);
}
export function getAccent(): AccentHint | "" {
  const v = typeof window === "undefined" ? null : read(ACCENT);
  return v && (ACCENTS as string[]).includes(v) ? (v as AccentHint) : "";
}
export function setAccent(a: AccentHint | "") {
  write(ACCENT, a || null);
}

/** `undefined` while rendering on the server / before hydration, `null` when no language was chosen yet. */
export function useLanguage(): ReplyLanguage | null | undefined {
  return useSyncExternalStore(subscribe, getLanguage, () => undefined);
}
export function useAccent(): AccentHint | "" {
  return useSyncExternalStore(subscribe, getAccent, () => "");
}
