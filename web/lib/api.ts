import type {
  AnalyzeOut,
  EvalResults,
  Fact,
  FactResult,
  Followup,
  Health,
  MessageOut,
  MessageSummary,
  ReaderView,
  Scenario,
  SuggestedFacts,
  Context,
  Reply,
} from "./types";

import { getSenderKey } from "./sender-key";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** `sender: true` adds the per-browser sender key (sender endpoints answer 403 without it). Reader endpoints stay open. */
async function request<T>(path: string, init?: RequestInit, sender = false): Promise<T> {
  let res: Response;
  try {
    const headers = new Headers(init?.headers);
    if (sender) headers.set("X-Sender-Key", getSenderKey());
    res = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Can't reach the Steve server. Is the API running?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export interface ConfirmOut {
  reader_token: string;
  reader_url: string;
}

export const api = {
  health: () => request<Health>("/health"),
  /** Global switch: admin-only. The operator's key travels in X-Admin-Key, never a sender key (D30). */
  setLlm: (enabled: boolean, adminKey: string) => {
    const init = json({ enabled });
    (init.headers as Record<string, string>)["X-Admin-Key"] = adminKey;
    return request<{ llm_switch: boolean; llm_enabled: boolean }>("/settings/llm", init);
  },

  createMessage: (b: { text: string; sender_name: string; context: Context }) =>
    request<SuggestedFacts>("/messages", json(b), true),
  confirm: (id: string, facts: Fact[]) => request<ConfirmOut>(`/messages/${id}/confirm`, json({ facts }), true),
  listMessages: () => request<MessageSummary[]>("/messages", undefined, true),
  getMessage: (id: string) => request<MessageOut>(`/messages/${id}`, undefined, true),
  followup: (id: string, lang?: string) =>
    request<Followup>(`/messages/${id}/followup${lang ? `?lang=${lang}` : ""}`, { method: "POST" }, true),
  // EventSource cannot set headers, so the stream (and only the stream) takes the key as a query parameter
  streamUrl: (id: string) => `${API_URL}/messages/${id}/stream?key=${encodeURIComponent(getSenderKey())}`,

  reader: (token: string) => request<ReaderView>(`/r/${token}`),
  sendReply: async (token: string, payload: { text?: string; audio?: Blob; lang_hint?: string }) => {
    const fd = new FormData();
    if (payload.text) fd.append("text", payload.text);
    if (payload.audio) fd.append("audio", payload.audio, "reply.wav");
    if (payload.lang_hint) fd.append("lang_hint", payload.lang_hint);
    return request<{ received: true }>(`/r/${token}/reply`, { method: "POST", body: fd });
  },

  check: (facts: Fact[], reply: string, message?: string, lang_hint?: string) =>
    request<FactResult[]>("/check", json({ facts, reply, lang_hint, message })),
  analyze: (reply: string, facts?: Fact[], message?: string, lang_hint?: string) =>
    request<AnalyzeOut>("/analyze", json({ reply, facts, lang_hint, message })),

  scenarios: () => request<Scenario[]>("/demo/scenarios"),
  seed: () => request<{ seeded: { message_id: string; reader_token: string; scenario: string }[] }>("/demo/seed", { method: "POST" }, true),
  evalResults: () => request<EvalResults>("/eval/results"),
};

export type { Reply };
