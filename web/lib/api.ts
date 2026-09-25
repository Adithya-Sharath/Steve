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

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Can't reach the Samjha server. Is the API running?");
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
  setLlm: (enabled: boolean) =>
    request<{ llm_switch: boolean; llm_enabled: boolean }>("/settings/llm", json({ enabled })),

  createMessage: (b: { text: string; sender_name: string; context: Context }) =>
    request<SuggestedFacts>("/messages", json(b)),
  confirm: (id: string, facts: Fact[]) => request<ConfirmOut>(`/messages/${id}/confirm`, json({ facts })),
  listMessages: () => request<MessageSummary[]>("/messages"),
  getMessage: (id: string) => request<MessageOut>(`/messages/${id}`),
  followup: (id: string, lang?: string) =>
    request<Followup>(`/messages/${id}/followup${lang ? `?lang=${lang}` : ""}`, { method: "POST" }),
  streamUrl: (id: string) => `${API_URL}/messages/${id}/stream`,

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
  seed: () => request<{ seeded: { message_id: string; reader_token: string; scenario: string }[] }>("/demo/seed", { method: "POST" }),
  evalResults: () => request<EvalResults>("/eval/results"),
};

export type { Reply };
