/**
 * Per-browser sender key. Generated once, kept in localStorage, sent as `X-Sender-Key` on every sender request.
 * It is a capability, not a password: whoever holds it can open that browser's messages. The server stores only its hash.
 * If storage is unavailable (private window) it lives in memory for the tab.
 */
const STORAGE_KEY = "samjha_sender_key";
let memoryKey: string | null = null;

function generate(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  const b64 = btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `sk_${b64}`;
}

export function getSenderKey(): string {
  if (typeof window === "undefined") return "";
  if (memoryKey) return memoryKey;
  try {
    const existing = window.localStorage.getItem(STORAGE_KEY);
    if (existing && /^sk_[A-Za-z0-9_-]{24,128}$/.test(existing)) return (memoryKey = existing);
  } catch {}
  const fresh = generate();
  try {
    window.localStorage.setItem(STORAGE_KEY, fresh);
  } catch {}
  return (memoryKey = fresh);
}
