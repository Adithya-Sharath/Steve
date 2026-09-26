/**
 * Steve Decode: a small typed client for the public API (docs/API.md, openapi.json). No dependencies; works in browsers and Node 18+ (global `fetch`, `FormData`, `Blob`).
 *
 *   const steve = new SteveClient({ baseUrl: "https://api.example.com" }); // a device key is created for you if you do not pass one
 *   const res = await steve.decode({ text: "yalla habibi come to the barking gate tree", accentHint: "ar", replyLanguage: "ml" });
 *   res.card.actions.where?.value            // "parking gate 3"
 *   if (res.decode_id) await steve.clarify({ decodeId: res.decode_id, questionIndex: 0, choice: "parking" });
 *
 * Response shapes are the contract: they only change with a decision record and a new openapi.json. Text only: nothing here plays or records audio;
 * `decodeAudio` uploads a clip you recorded (WAV recommended, at most 4 MB and 30 s).
 */

// ---- types (mirror openapi.json) ----------------------------------------------------------------------------------------------------------------

export type ReplyLanguage = "en" | "ml" | "hi" | "ur" | "tl" | "bn";
export type AccentHint = "ar" | "hi" | "ml" | "tl";

/** Offsets are Unicode CODE POINTS of the text (not UTF-16 units): slice with `Array.from(text)`. */
export interface Span {
  start: number;
  end: number;
  text: string;
}
export interface Change {
  span: Span;
  heard: string;
  meant: string;
  reason: string;
  confidence: number;
  source: string;
}
export interface PhraseHit {
  span: Span;
  phrase: string;
  literal: string;
  social_meaning: string;
  category: string;
}
export interface ActionValue {
  value: string;
  evidence: Span | null;
}
export interface Actions {
  where: ActionValue | null;
  when: ActionValue | null;
  what: ActionValue | null;
  how_much: ActionValue | null;
}
export interface Clarify {
  span: Span;
  options: string[];
  question: string;
  slot: string;
}
export interface DecodedCard {
  original_text: string;
  plain_english: string;
  changes: Change[];
  phrases: PhraseHit[];
  actions: Actions;
  clarify: Clarify[];
  /** questions answered with "not_sure": the slot stays empty */
  skipped: Clarify[];
  tips: string[];
  /** internal; never show it as a score */
  confidence: number;
  accent_used: string | null;
  path: string;
}
export interface TranslatedPhrase {
  phrase: string;
  literal: string;
  social_meaning: string;
}
export interface TranslatedCard {
  language: ReplyLanguage;
  provider: string;
  /** always true when present: a translation that changed a number is never returned */
  verified_numbers: boolean;
  plain_english: string;
  where: string | null;
  when: string | null;
  what: string | null;
  how_much: string | null;
  phrases: TranslatedPhrase[];
  questions: string[];
  tip: string | null;
}
export interface DecodeResponse {
  /** null only when a voice note could not be decoded (see `notes`) */
  card: DecodedCard | null;
  translation: TranslatedCard | null;
  transcript: string | null;
  /** present only while a clarifying question is open */
  decode_id: string | null;
  notes: string[];
  say_back: string[];
}
export interface DecodeExample {
  id: string;
  label: string;
  request: { text: string; accent_hint?: AccentHint | null; reply_language?: ReplyLanguage | null };
  response: DecodeResponse;
}
export interface DecodeExamples {
  examples: DecodeExample[];
  computed_live: boolean;
}
export interface DecodeHealth {
  typed: boolean;
  voice: boolean;
  translation: { available: boolean; languages: Record<string, string[]>; budget_remaining: number };
  languages: ReplyLanguage[];
  accent_hints: AccentHint[];
  budget: { stt_remaining: number; stt_cap: number };
  limits: { audio_seconds: number; audio_bytes: number; clarify_minutes: number };
}

export interface InspectResult {
  path: "typed" | "voice";
  tokens: { i: number; text: string; start: number; end: number }[];
  glossary: { phrase: string; span: Span; category: string }[];
  slots: { token: string; kind: string; expects: string[]; trigger: string }[];
  examined: {
    token: string;
    slot: string;
    decision: "fits" | "no_alternative" | "keep" | "rewrite" | "clarify";
    best: string | null;
    margin: number;
    options: string[];
    candidates: { word: string; score: number }[];
    original_score: number;
  }[];
  effective_words: string[];
  unresolved_tokens: number[];
  card: DecodedCard;
}
export interface DecodeEval {
  available: boolean;
  message: string | null;
  generated_from: string[];
  caveats: string[];
  sections: { id: string; title: string; label: string; note: string | null; rows: { metric: string; value: string; detail: string | null }[] }[];
}

export interface DecodeOptions {
  accentHint?: AccentHint;
  replyLanguage?: ReplyLanguage;
}

/** Any non-2xx answer. `detail` is a sentence you can show; `retryAfter` (seconds) is set for 429. */
export class SteveApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public retryAfter?: number,
  ) {
    super(detail);
    this.name = "SteveApiError";
  }
}

export interface SteveClientOptions {
  /** e.g. "https://api.example.com" (no trailing slash needed) */
  baseUrl: string;
  /** `wk_` + 24 to 128 URL-safe characters. Omit to have one generated (keep `client.workerKey` to reuse it on the next visit). */
  workerKey?: string;
  /** inject a different fetch (tests, Node < 18) */
  fetch?: typeof fetch;
}

/** A fresh device key. It is a capability, not a password: whoever has it counts against that worker's daily limit. The server stores nothing about it. */
export function newWorkerKey(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return `wk_${btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")}`;
}

export class SteveClient {
  readonly baseUrl: string;
  readonly workerKey: string;
  private readonly f: typeof fetch;

  constructor(opts: SteveClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.workerKey = opts.workerKey ?? newWorkerKey();
    this.f = opts.fetch ?? ((...a) => fetch(...a));
  }

  private async call<T>(path: string, init: RequestInit = {}, withKey = true): Promise<T> {
    const headers = new Headers(init.headers);
    if (withKey) headers.set("X-Worker-Key", this.workerKey);
    const res = await this.f(`${this.baseUrl}${path}`, { ...init, headers });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
      } catch {
        /* keep the status text */
      }
      const retry = res.headers.get("Retry-After");
      throw new SteveApiError(res.status, detail, retry ? Number(retry) : undefined);
    }
    return (await res.json()) as T;
  }

  /** Decode a typed or pasted message. */
  decode(input: { text: string } & DecodeOptions): Promise<DecodeResponse> {
    return this.call<DecodeResponse>("/decode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: input.text, accent_hint: input.accentHint, reply_language: input.replyLanguage }),
    });
  }

  /** Decode a voice note (a Blob or File, at most 4 MB and 30 s). If voice is off the response has `card: null` and a note telling the user to type. */
  decodeAudio(audio: Blob, opts: DecodeOptions = {}): Promise<DecodeResponse> {
    const fd = new FormData();
    fd.append("audio", audio, "note.wav");
    if (opts.accentHint) fd.append("accent_hint", opts.accentHint);
    if (opts.replyLanguage) fd.append("reply_language", opts.replyLanguage);
    return this.call<DecodeResponse>("/decode", { method: "POST", body: fd });
  }

  /** Answer one open question. `choice` is one of `card.clarify[questionIndex].options`, or "not_sure". Returns the updated response. */
  clarify(input: { decodeId: string; questionIndex: number; choice: string }): Promise<DecodeResponse> {
    return this.call<DecodeResponse>("/decode/clarify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decode_id: input.decodeId, question_index: input.questionIndex, choice: input.choice }),
    });
  }

  /** What works right now (typed, voice, translation, languages, today's budgets). No key needed, no secrets in it. */
  health(): Promise<DecodeHealth> {
    return this.call<DecodeHealth>("/decode/health", {}, false);
  }

  /** Every stage of one decode (tokens, glossary, critical slots, candidates and decisions, the card). No key needed, nothing stored. */
  inspect(input: { text: string; accentHint?: AccentHint; path?: "typed" | "voice" }): Promise<InspectResult> {
    return this.call<InspectResult>(
      "/decode/inspect",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: input.text, accent_hint: input.accentHint, path: input.path ?? "typed" }) },
      false,
    );
  }

  /** The Decode evaluation numbers, each section with the label that must travel with it. No key needed. */
  evaluation(): Promise<DecodeEval> {
    return this.call<DecodeEval>("/decode/eval", {}, false);
  }

  /** Six ready-made inputs with the cards the engine returns for them right now (for demo buttons). No key needed. */
  examples(): Promise<DecodeExamples> {
    return this.call<DecodeExamples>("/decode/examples", {}, false);
  }
}
