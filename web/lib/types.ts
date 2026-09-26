// Mirrors engine/steve_engine/schema.py and api/app/schemas.py — keep in sync.

export type FactType = "dose" | "frequency" | "timing" | "duration" | "date" | "amount" | "condition";
export type Status = "understood" | "wrong" | "missing" | "negated" | "unclear";
export type Context = "pharmacy" | "workplace" | "visa" | "school" | "other";

export interface ConditionValue {
  trigger: string;
  action: "stop" | "call" | "come_back" | "continue" | "avoid";
  text: string;
}

export interface Fact {
  id: string;
  type: FactType;
  value: number | string | string[] | ConditionValue;
  unit: string | null;
  critical: boolean;
  label: string;
}

/** Offsets are Python code points; use `toCodePoints()` in lib/spans.ts to slice. */
export interface Span {
  start: number;
  end: number;
  text: string;
}

export interface MatchedTerm {
  token: string;
  lexeme: string;
  category: string;
  lang: string;
  score: number;
  kind: string;
}

export interface FactResult {
  fact_id: string;
  status: Status;
  heard_value: unknown;
  expected_value: unknown;
  evidence: Span[];
  confidence: number;
  reason: string;
  matched_terms: MatchedTerm[];
  /** reply-level warnings, e.g. "copied" (the reader pasted the sender's message back) */
  flags?: string[];
}

export interface Reply {
  id: string;
  text: string;
  source: "text" | "voice";
  created_at: string;
  results: FactResult[];
}

export interface LatestFact {
  fact_id: string;
  status: Status;
  reply_id: string | null;
  result: FactResult | null;
}

export type Aggregate = Record<Status | "total", number>;

export interface MessageOut {
  id: string;
  text: string;
  sender_name: string;
  context: Context;
  confirmed: boolean;
  demo: boolean;
  created_at: string;
  reader_token: string | null;
  reader_url: string | null;
  facts: Fact[];
  replies: Reply[];
  latest: LatestFact[];
  aggregate: Aggregate;
}

export interface MessageSummary {
  id: string;
  text: string;
  sender_name: string;
  context: Context;
  confirmed: boolean;
  demo: boolean;
  created_at: string;
  reader_url: string | null;
  fact_count: number;
  reply_count: number;
  aggregate: Aggregate;
}

export interface SuggestedFacts {
  message_id: string;
  suggested_facts: Fact[];
  extractor: "regex" | "llm";
  note: string | null;
}

export interface ReaderView {
  text: string;
  sender_name: string;
  context: Context;
  stt_enabled: boolean;
  prompt: { title: string; body: string };
}

export interface Health {
  status: string;
  llm_enabled: boolean;
  llm_switch: boolean;
  llm_key_present: boolean;
  admin_toggle_available: boolean;
  budget?: { llm_cap: number; llm_remaining: number; stt_cap: number; stt_remaining: number };
  stt_enabled: boolean;
  lexicon: { entries: number; by_language: Record<string, number> };
  version: string;
}

export interface Followup {
  draft: string;
  lang: string;
  failed: { fact_id: string; label: string; status: Status }[];
}

export interface Preset {
  id: string;
  kind: "correct" | "subtle_mistake" | "negation_flip";
  lang_mix: string;
  label: string;
  text: string;
  expected: Record<string, Status>;
}

export interface Scenario {
  id: string;
  title: string;
  context: Context;
  sender_name: string;
  text: string;
  facts: Fact[];
  presets: Preset[];
}

export interface AnalyzeOut {
  tokens: { text: string; norm: string; start: number; end: number; kind: string; sentence: number }[];
  matches: {
    start: number;
    end: number;
    text: string;
    category: string;
    value: number | string | boolean;
    lang: string;
    score: number;
    kind: string;
    canonical: string;
    ambiguous_with: { lang: string; category: string; value: string }[];
    negated: boolean;
  }[];
  slots: {
    type: FactType;
    value: number | string;
    unit: string | null;
    text: string;
    confidence: number;
    inferred: boolean;
    negated: boolean;
    spans: Span[];
  }[];
  bare_numbers: string[];
  results?: FactResult[];
}

// ---- evaluation (eval/results/latest.json) ----
export interface EvalBucket {
  n: number;
  correct: number;
  accuracy: number;
  false_understood: number;
  false_understood_rate: number;
  false_understood_denominator: number;
}
export interface EvalSystem {
  available: boolean;
  overall: EvalBucket | null;
  by_language: Record<string, EvalBucket>;
  by_type: Record<string, EvalBucket>;
  by_source: Record<string, EvalBucket>;
  confusion: Record<string, Record<string, number>>;
  consistency?: { mean_agreement: number; items: number; runs: number } | null;
  note?: string;
}
export interface EvalCase {
  reply_id: string;
  message_id: string;
  fact_id: string;
  fact_label: string;
  lang_mix: string;
  fact_type: FactType;
  synthetic: boolean;
  reply_text: string;
  gold: Status;
  engine: { status: Status; reason: string };
  baseline: { status: Status | null; agreement?: number } | null;
}
export interface EvalResults {
  available: boolean;
  message?: string;
  generated_at?: string;
  n_fact_checks?: number;
  n_replies?: number;
  n_synthetic?: number;
  n_handwritten?: number;
  engine?: EvalSystem;
  baseline?: EvalSystem;
  cases?: EvalCase[];
  caveats?: string[];
}
