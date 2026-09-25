# Claude Code Build Prompt — "Samjha" (Mixed-Language Teach-Back)

> Paste everything below the line into Claude Code, from an empty folder that will become the GitHub repo.
> "Samjha" (Hindi/Urdu for "understood?") is a working name. Rename freely.

---

You are building a complete, production-quality hackathon project end to end in this repository. Work autonomously through the phases below, commit after each phase, and run the tests before moving on. When something is ambiguous, pick the sensible option, write it down in `DECISIONS.md`, and keep going.

## 0. Context (read carefully; it governs every design decision)

**Hackathon:** BitNBuild'26, UAE regional round. Deliverables: a public GitHub repo with a comprehensive `README.md` (project details, tech stack, features, setup), plus a demo video of at most 2 minutes.

**Problem statement we are solving (AI/ML track):**
> "Language tools learn one clean official version of a language, then meet people who switch tongues within a sentence, spell by ear, and write one language in another's script."

**Our reading of it:**
- Most teams will build a translator or normalizer that converts mixed language into "proper" English. We explicitly do NOT, because that forces people back into the one clean version the statement criticises.
- We fix the problem at a different moment: the *response*. When someone sends an important instruction (medicine dose, visa deadline, safety rule), the reader replies "ok 👍" and nobody knows if it was understood.
- We build for someone else in the sentence: the *sender*, who can't tell whether the message landed.

**The product:** the digital version of the clinical **teach-back** method.
1. The sender writes an important message.
2. Key facts are extracted into typed slots, and the sender confirms them.
3. The reader explains the message back in their own words, by voice or text, in any mix of Manglish, Hinglish, Arabizi or Taglish, spelled however they like.
4. Our engine checks every key fact in that explanation: `understood`, `wrong`, `missing`, `negated` or `unclear`.
5. The sender sees a fact-by-fact result and re-explains only what failed. The reader is never shown a score.

**Evidence (use in the README and the landing page; keep the links):**
- About 19% of patients' answers about their own prescription labels were wrong. Dose (52%) and frequency (28%) errors dominate. https://www.aafp.org/pubs/afp/issues/2007/0615/p1851a.html
- Teach-back cut comprehension deficits from 49% to 11.9% in a 483-patient emergency department study, but that study **excluded patients with language barriers**. https://link.springer.com/article/10.1186/s12245-020-00306-9
- AHRQ recommends teach-back. https://www.ahrq.gov/health-literacy/improve/precautions/tool5.html
- LLMs score 5–12 F1 points worse on romanized Indian-language health messages than on native script, because of spelling noise. https://arxiv.org/html/2512.10780v1
- UAE residents: Indians ~38%, Pakistanis ~17%, Bangladeshis ~7%, Filipinos ~7% (GMI 2026). https://www.globalmediainsight.com/blog/uae-population-statistics/
- Closest competitor: Hippocratic AI, whose AI voice agents make post-discharge calls, active in the UAE via Burjeel. We differ: we are a checking layer any sender (human or AI) can use, focused on romanized code-mixed replies, with exact checks on numbers.

## 1. Non-negotiable principles (this is what makes it NOT an AI wrapper)

1. **An LLM is never the final judge of a safety-critical fact.** Numbers, doses, frequencies, durations, dates, amounts and negations are decided by deterministic code in `engine/` that we write and test.
2. **The engine must run fully with zero API keys.** LLMs are optional helpers only: (a) suggesting facts from the sender's message, which the sender confirms, and (b) the evaluation baseline. Speech-to-text is optional; typed replies always work.
3. **No translation features anywhere.** We never translate the message or the reply. The reader's words are shown verbatim.
4. **A false "understood" is the worst possible error.** When confidence is low, return `unclear`, never `understood`.
5. **Every result must be explainable.** Each fact result carries the exact evidence span(s) from the reply and a human-readable reason.
6. **The wrapper test must pass:** with `LLM_ENABLED=false`, the full demo (typed facts, typed replies) still works end to end. Build a visible toggle for this in the UI (see §6).

## 2. Tech stack

- **Monorepo** with: `engine/` (pure Python package), `api/` (FastAPI), `web/` (Next.js), `data/`, `eval/`.
- **Engine:** Python 3.11+, `rapidfuzz`, `pyyaml`, `pydantic`. Optional: `sentence-transformers` with `intfloat/multilingual-e5-small`, loaded lazily for the condition-fact fallback.
- **API:** FastAPI, Pydantic v2, SQLModel on SQLite, `uvicorn`, `httpx`, `python-dotenv`.
- **LLM (optional):** Google Gemini via the official `google-genai` SDK. Model name configurable via `GEMINI_MODEL`; check the SDK docs for the current recommended model id and use strict JSON/structured output.
- **Speech-to-text (optional):** Sarvam AI Saaras for Malayalam-English and Hindi-English. **Read the current API docs at https://docs.sarvam.ai before implementing**; do not guess endpoints or parameters. We want verbatim/romanized (transliterated) output that preserves spoken numbers, NOT translation. Wrap it behind an interface `SpeechToText` with a `NullSpeechToText` fallback.
- **Web:** Next.js (latest stable, App Router, TypeScript strict), Tailwind CSS, shadcn/ui, Framer Motion, lucide-react, Recharts (eval charts), `qrcode.react` (share link QR), `sonner` (toasts). Fonts via `next/font`: Geist Sans + Geist Mono for UI, plus a characterful display serif for headlines (e.g. Instrument Serif).
- **Tooling:** `pytest`, `ruff`; ESLint + Prettier; `docker-compose.yml` to run api + web together; a `Makefile` with `make dev`, `make test`, `make eval`, `make seed`.

## 3. Repository layout

```
samjha/
├── engine/
│   ├── samjha_engine/
│   │   ├── __init__.py
│   │   ├── schema.py        # Fact, FactResult, Span, Status enums (pydantic)
│   │   ├── lexicon.yaml     # multilingual fact-bearing vocabulary (see §4.2)
│   │   ├── lexicon.py       # load + index lexicon
│   │   ├── normalize.py     # cleaning, tokenization with char offsets
│   │   ├── matcher.py       # spelling-by-ear matching (fuzzy + sound key)
│   │   ├── negation.py      # negation scope detection per language
│   │   ├── slots.py         # slot fillers: dose, frequency, timing, duration, date, amount, condition
│   │   ├── compare.py       # exact comparison + status + reason
│   │   ├── fallback.py      # optional embedding similarity for condition facts
│   │   └── check.py         # public entry: check_reply(facts, reply_text) -> list[FactResult]
│   ├── tests/               # extensive pytest suite (see §4.6)
│   └── pyproject.toml
├── api/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, routes
│   │   ├── db.py            # SQLModel models: Message, Fact, ReaderLink, Reply, FactResultRow
│   │   ├── routes/          # messages.py, reader.py, eval.py, demo.py, health.py
│   │   ├── services/
│   │   │   ├── extractor.py # LLM fact suggestion + regex fallback extractor
│   │   │   ├── stt.py       # SpeechToText interface, SarvamSTT, NullSpeechToText
│   │   │   └── followup.py  # builds a re-explain draft ONLY for failed facts (sender's language, template-based)
│   │   └── settings.py      # env: LLM_ENABLED, GEMINI_API_KEY, GEMINI_MODEL, SARVAM_API_KEY, DATABASE_URL, PUBLIC_WEB_URL
│   ├── tests/
│   └── pyproject.toml
├── web/                     # Next.js app (see §6)
├── data/
│   ├── scenarios.json       # demo scenarios (see §7)
│   ├── messages.json        # eval messages with gold facts
│   └── replies.csv          # eval replies with per-fact gold labels
├── eval/
│   ├── generate.py          # expands hand-written templates into labeled variants
│   ├── run_engine.py
│   ├── run_baseline.py      # Gemini baseline, 5 runs per item for consistency
│   ├── metrics.py
│   └── results/             # JSON outputs consumed by the web eval page
├── docs/
│   ├── architecture.md
│   └── demo-script.md
├── DECISIONS.md
├── README.md
├── .env.example
├── docker-compose.yml
└── Makefile
```

## 4. The engine (the heart of the project; build it first and test it hardest)

### 4.1 Schemas (`schema.py`)

```python
class FactType(str, Enum):
    dose = "dose"            # value: number, unit: tablet|ml|puff|drop|capsule|spoon
    frequency = "frequency"  # value: times per day (float, e.g. 0.5 for alternate days)
    timing = "timing"        # value: set of tags {before_food, after_food, morning, noon, evening, night, bedtime, empty_stomach}
    duration = "duration"    # value: number of days (weeks*7, months*30)
    date = "date"            # value: ISO date or weekday
    amount = "amount"        # value: number + currency
    condition = "condition"  # value: {trigger: str, action: stop|call|come_back|continue, text: str}

class Status(str, Enum):
    understood = "understood"; wrong = "wrong"; missing = "missing"; negated = "negated"; unclear = "unclear"

class Fact(BaseModel):
    id: str; type: FactType; value: Any; unit: str | None = None
    critical: bool = True; label: str  # human label e.g. "2 tablets"

class Span(BaseModel):
    start: int; end: int; text: str      # char offsets into the ORIGINAL reply text

class FactResult(BaseModel):
    fact_id: str; status: Status
    heard_value: Any | None; expected_value: Any
    evidence: list[Span]                 # what in the reply supports the decision
    confidence: float                    # 0..1
    reason: str                          # plain English, e.g. "Heard 'oru week' = 7 days; expected 5 days"
    matched_terms: list[dict]            # [{"token": "randu", "lexeme": "2", "lang": "ml", "score": 92}]
```

`check_reply(facts: list[Fact], reply: str, lang_hint: str | None = None) -> list[FactResult]` is the only public function the API calls.

### 4.2 Lexicon (`lexicon.yaml`)

A YAML file of **fact-bearing words only**, in romanized form (plus Arabic-Indic digits and Arabic-script numerals where trivial). Each entry: `canonical`, `category`, `value`, `lang`, `variants` (spellings by ear), `verified` (bool). Categories: `number`, `unit`, `frequency_phrase`, `timing`, `duration_unit`, `negation`, `action_stop`, `action_call`, `action_return`, `symptom`, `food_relation`, `filler`.

Seed it with at least these; include common by-ear spelling variants. **Mark every entry `verified: false` unless it is plain English**, and generate `LEXICON_REVIEW.md` listing all entries grouped by language, so our native-speaker teammates can verify them. Do not invent obscure vocabulary; if unsure, leave it out.

- **English:** one…ten, twelve, fifteen, twenty, thirty, half; tablet/tab/pill/capsule/ml/spoon/drop/puff; once/twice/thrice, "x times", "every N hours" (24/N per day); morning/afternoon/evening/night/bedtime; before/after food|meal|eating, empty stomach; day(s)/week(s)/month(s); don't/do not/never/no/not; stop/call/come back.
- **Malayalam (romanized):** onnu 1, randu/rendu 2, moonu 3, naalu 4, anju 5, aaru 6, ezhu 7, ettu 8, ombathu 9, pathu 10; gulika (tablet); neram (times, as in "randu neram" = twice); divasam (day), aazhcha (week), maasam (month); raavile (morning), uchakku (noon), vaikittu/vaikunneram (evening), raathri (night); kazhinju (after) as in "food kazhinju" / "bhakshanam kazhinju"; munpu (before); venda/vendaa (don't), alla, illa (not); nirthuka/nirthanam/nirthu (stop); oru (one/a) as in "oru week".
- **Hindi/Urdu (romanized):** ek 1, do 2, teen 3, chaar 4, paanch 5, chhe 6, saat 7, aath 8, nau 9, das 10; goli (tablet); baar (times) as in "do baar" = twice; din (day), hafta (week), mahina (month); subah (morning), dopahar (noon), shaam (evening), raat (night); khane ke baad (after food), khane se pehle (before food), baad/pehle; nahi/nahin, mat, na (negation); band karo/rok do (stop).
- **Arabizi (Gulf, romanized with digits):** wa7ed 1, ithnain/ethnain/itnen 2, thalatha/tlatha 3, arba3a 4, khamsa 5, sitta 6, sab3a 7, thamanya 8, tis3a 9, 3ashra 10; habba/7abba (pill); marra/marratain (once/twice); yom/youm (day), ayyam (days), esbou3/usbu3 (week), shahar (month); sabah (morning), masa (evening), lail (night); ba3d al akl (after food), gabl al akl (before food); la, ma, mub/mo (negation); wagif/waqqif (stop). Also map Arabic-Indic digits ٠-٩ to 0-9.
- **Tagalog:** isa 1, dalawa 2, tatlo 3, apat 4, lima 5, anim 6, pito 7, walo 8, siyam 9, sampu 10; tableta (tablet); beses (times) as in "dalawang beses" = twice; araw (day), linggo (week), buwan (month); umaga (morning), tanghali (noon), hapon (afternoon), gabi (night); pagkatapos kumain (after eating), bago kumain (before eating); huwag/wag, hindi (negation); itigil/tigil (stop).
- Handle linkers and suffixes by ear: e.g. Tagalog "dalawang" (dalawa + -ng), Malayalam suffix forms. Implement suffix-stripping rules per language in `matcher.py`, driven by a small config, not hard-coded if-chains.

### 4.3 Matching words by ear (`matcher.py`)

- Tokenize while keeping character offsets into the original text (needed for highlights).
- For each token (and bigram/trigram, for phrases like "khane ke baad", "food kazhinju", "ba3d al akl"), find lexicon candidates using:
  1. exact match on canonical/variants;
  2. `rapidfuzz` ratio / partial ratio with length-aware thresholds (short tokens need near-exact matches to avoid "do" vs "no" confusions);
  3. a simple **sound key**: lowercase; collapse doubled letters; map digit-letters (3→a/ayn, 7→h, 2→a/hamza, 5→kh); unify vowels (aa→a, ee/ii→i, oo/uu→u); unify common by-ear consonant swaps (th/t, dh/d, v/w, ph/f, z/j, q/k).
- Return ranked matches with scores; keep ambiguity (a token may be a number in one language and something else in another). Use `lang_hint` and neighbouring matched tokens (language context window) to break ties.
- Never match purely numeric-looking English words inside unrelated words (e.g. "done" must not match "one").

### 4.4 Slot filling (`slots.py`) and negation (`negation.py`)

- **dose:** number (word or digit) within a window of a unit word; also "half" (0.5); "randu gulika", "do goli", "dalawang tableta", "2 tabs", "ithnain habba".
- **frequency:** "twice", "2 times", "do baar", "randu neram", "marratain", "dalawang beses", "every 8 hours" (=3); also count distinct time-of-day words when no explicit frequency is present ("raavile vaikittu" → morning + evening → 2/day, "subah shaam" → 2/day), but mark confidence lower for this inference.
- **timing:** set of tags from time-of-day and food-relation phrases.
- **duration:** number + duration unit; "oru week" → 7 days; "ek hafta" → 7; "isang linggo" → 7; "5 divasam" → 5; "paanch din" → 5.
- **date / amount:** digits and number words + month names / weekdays / currency (AED, dirham, dhs, rs, rupees, peso).
- **condition:** detect trigger (symptom word or the fact's trigger text via lexicon + fuzzy) and action (stop/call/return) nearby.
- **negation:** per-language negation words with scope rules (English/Tagalog/Arabic: negator before verb, forward window; Malayalam "venda"/"illa" and Hindi "mat"/"nahi" often attach AFTER or before the verb, so use a bidirectional window). If a matched action (e.g. "stop") is in negation scope, the condition becomes `negated`. Also handle "nirthanda" / "band mat karo" style negated stop.

### 4.5 Compare and decide (`compare.py`, `check.py`)

- Numeric slots: exact equality (with unit normalization). A conflicting value is `wrong` with a reason; no value is `missing`.
- Timing: set comparison. Missing a required tag = `wrong` if an opposite tag is present (before vs after food), else `missing`.
- Condition: trigger and action both present and not negated = `understood`; negated = `negated`; trigger present, action absent = `unclear`.
- Optional embedding fallback (`fallback.py`) is **only** for condition facts with no lexicon hit, and it can only raise a result to `unclear` or `understood` if the similarity is above a threshold calibrated on the eval set (store the threshold in config). It can never override a numeric decision.
- Confidence: a combination of match scores, inference type (explicit vs inferred) and ambiguity. Below `UNCLEAR_THRESHOLD` (configurable, default 0.6) → `unclear`.
- Every result gets evidence spans and a plain-English `reason`.

### 4.6 Tests (must pass before moving on)

Write at least 60 pytest cases, including these exact ones:
- "randu gulika, food kazhinju, raavile vaikittu, oru week" against facts {dose 2 tablet, timing after_food, frequency 2, duration 5} → dose understood, timing understood, frequency understood, duration **wrong** (heard 7, expected 5).
- "do goli khane ke baad subah shaam paanch din" → all understood.
- "dalawang tableta pagkatapos kumain, dalawang beses, limang araw" → all understood (note linker -ng).
- "ithnain habba ba3d al akl marratain 5 ayyam" → all understood.
- Condition "stop if rash": reply "rash vannal nirthanam" → understood; "rash vannalum nirthanda" → **negated**; reply with no mention → missing.
- "done" must NOT match "one"; "no" must NOT match "do"; "to" must not become 2.
- Spelling variants: "rendu", "randu", "rndu" → 2; "paanch", "panch" → 5; "arba3a", "arbaa" → 4.
- Low-evidence reply "ok ok sheri" → every fact `missing` or `unclear`, never `understood`.
- Evidence spans point to the correct character offsets in the original string (including emoji and mixed casing).

## 5. API (FastAPI)

| Method & path | Purpose |
|---|---|
| `GET /health` | Status, plus flags `llm_enabled`, `stt_enabled` |
| `POST /messages` | Body `{text, sender_name, context: "pharmacy"|"workplace"|"visa"|"school"|"other"}` → `{message_id, suggested_facts[]}` via LLM if enabled, else regex extractor |
| `POST /messages/{id}/confirm` | Body `{facts[]}` (edited/confirmed) → `{reader_token, reader_url}` |
| `GET /messages` | List sender's messages with aggregate status |
| `GET /messages/{id}` | Message, facts, replies, latest results |
| `GET /r/{token}` | Reader view data: message text, sender name, prompt copy. No facts, no scores |
| `POST /r/{token}/reply` | multipart: `text` or `audio` (webm/ogg/wav). If audio and STT enabled → transcribe verbatim → `check_reply` → store. Returns `{received: true}` only |
| `GET /messages/{id}/stream` | Server-Sent Events: pushes new replies/results live to the sender dashboard |
| `POST /messages/{id}/followup` | Returns a draft re-explanation covering ONLY failed facts, in the sender's own language, template-based (no translation) |
| `POST /check` | Stateless: `{facts, reply}` → results (used by the landing-page playground and eval) |
| `GET /eval/results` | Latest eval JSON for the web eval page |
| `POST /demo/seed` | Loads `data/scenarios.json` into the DB |
| `POST /settings/llm` | Toggle `LLM_ENABLED` at runtime (for the wrapper-test toggle in the UI) |

Store audio only in memory for transcription; never persist it. Add rate limiting on reader replies. CORS for the web origin.

## 6. Web app: beautiful, animated, demo-ready

### 6.1 Design direction

- **Mood:** calm, trustworthy, human, with a clinical-grade clarity feel, not a generic AI purple gradient. Think "Linear meets a modern health app."
- **Palette:** warm off-white background (light) and deep ink (dark), both fully supported via CSS variables and a theme toggle. Primary accent: a deep teal. Status colors (accessible contrast in both themes): understood = emerald, wrong = rose, missing = amber, negated = violet, unclear = slate-blue. Use these consistently everywhere, and never rely on color alone: every status also has an icon and a label.
- **Type:** display serif for hero and section headlines; Geist Sans for UI; Geist Mono for transcripts, tokens and numbers.
- **Surfaces:** soft layered cards, 1px hairline borders, subtle noise texture, generous whitespace, 16–24px radii.
- **Motion (Framer Motion):** purposeful and physical, not decorative noise.
  - staggered fade/slide-in for lists;
  - `layout` animations when fact cards reorder by status;
  - spring pop when a fact resolves;
  - an animated highlight "sweep" across transcript spans;
  - a waveform that reacts to mic input while recording;
  - number ticker animations on metric tiles;
  - page transitions.
  - Respect `prefers-reduced-motion` everywhere.
- **Responsive:** the reader page is designed mobile-first (it's opened from WhatsApp); the sender dashboard is desktop-first but works on mobile.
- **Quality bar:** no layout shift, skeleton loaders, empty states with illustration and copy, error states with retry, keyboard accessible, focus rings, aria labels, Lighthouse accessibility ≥ 95.

### 6.2 Pages

1. **`/` Landing**
   - Hero: headline like *"'ok 👍' isn't understanding."* with a subline explaining teach-back in any language mix.
   - **Animated hero demo:** a looping, scripted sequence. A pharmacist's message appears → a WhatsApp-style bubble with a Manglish voice reply types in → key-fact chips light up one by one (✓ dose, ✓ timing, ✓ frequency, ✗ duration "oru week ≠ 5 days", ! warning missing).
   - Sections: the problem (with the cited stats as animated counters and source links), how it works (4-step animated diagram), "why not just translate" (a short, sharp comparison), "why this isn't an AI wrapper" (the wrapper-test toggle preview), languages supported, CTA to try the demo.
   - **Live playground:** pick a scenario, type any reply, see results instantly via `POST /check`.
2. **`/app` Sender dashboard**
   - List of sent messages as cards with aggregate status rings (e.g. 3/5 understood), filters, and a "New message" button. Includes a seeded demo button.
3. **`/app/new` Composer**
   - Message editor with a context picker (pharmacy, workplace, visa, school).
   - "Find key facts" → facts animate in as editable chips (type icon, value, unit, critical toggle). Users can add/remove facts manually (this path works with the LLM off).
   - Confirm → share sheet with the reader link, a QR code, "Copy WhatsApp message" (prefilled text with link) and a "Simulate reply" button for demos.
4. **`/app/m/[id]` Results**
   - Left: the original message with the facts highlighted inline. Right: live replies via SSE.
   - Each reply shows the verbatim transcript (mono font) with evidence spans highlighted in the matching status color. Hovering a fact card highlights its span, and vice versa.
   - Fact cards flip from a pending shimmer to their status with a spring animation, with the reason text ("Heard 'oru week' = 7 days · expected 5 days") and matched terms shown as tiny tokens (`randu → 2 · ml · 94`).
   - "Draft follow-up" button → modal with a re-explanation covering only failed facts, editable, copyable.
   - A small "LLM off" badge when the wrapper-test toggle is off.
5. **`/r/[token]` Reader page** (mobile-first, zero login, reassuring, no scores ever)
   - Sender name + message in a clean card.
   - Friendly prompt, shown in simple English with small language hints ("Tell us in your own words: any language is fine. Malayalam, Hindi, Arabic, Tagalog, English, or a mix.").
   - Huge circular record button with a live waveform and timer (MediaRecorder API). Stop and re-record. Text box alternative.
   - Submit → a warm thank-you screen with a subtle confetti or check animation.
   - Must work if STT is disabled: hide voice and show text only, gracefully.
6. **`/eval` Evaluation dashboard**
   - Metric tiles for ours vs the baseline: fact-level accuracy, **false "understood" rate** (the headline metric, visually emphasised), consistency across 5 baseline runs.
   - Bar chart per language (Manglish, Hinglish, Arabizi, Taglish) and per fact type.
   - A confusion matrix of gold vs predicted status.
   - An error explorer table: filter to cases where either system was wrong, showing the reply, gold labels, our prediction with reason, and the baseline prediction.
   - All numbers load from `eval/results/*.json`. **Never hard-code or fabricate numbers;** if results are missing, show an empty state telling the user to run `make eval`.
7. **`/how-it-works`**
   - An animated pipeline diagram: clean → match by ear → negation → slots → compare → decide.
   - An interactive "type a reply and watch each stage" inspector showing tokens, lexicon matches with scores, slots and final results.
   - The **wrapper test**: a toggle that turns the LLM off and shows everything still working.

### 6.3 Frontend engineering

- A typed API client in `web/lib/api.ts` generated from shared TypeScript types mirroring the Pydantic schemas.
- Server components where sensible, client components for interactive parts, React Query (TanStack Query) for data fetching.
- `NEXT_PUBLIC_API_URL` env var.
- A reusable `<StatusBadge>`, `<FactCard>`, `<Transcript highlights>`, `<Waveform>`, `<MetricTile>`, `<PipelineDiagram>`.
- Storybook is not needed. Keep components clean.

## 7. Demo data and evaluation

### 7.1 `data/scenarios.json` (at least 4, realistic, UAE-relevant)

1. **Pharmacy:** "Take 2 tablets after food, twice a day, for 5 days. Stop taking them and call us if you get a rash."
2. **Construction site safety:** "Drink 1 bottle of water every hour. Take a 15-minute break in the shade at 12:30. If you feel dizzy, stop work and tell the supervisor."
3. **Visa/HR:** "Submit your passport copy and 2 photos by Thursday. The fee is 150 AED. Do not travel until your visa is stamped."
4. **School circular:** "The school trip is on Monday. Send 30 AED and the signed form by Friday. Children must bring a water bottle."

Each scenario has gold facts plus 3 pre-written "simulate reply" presets (one fully correct, one with a subtle mistake, one with a negation flip) across different language mixes, used for the demo video.

### 7.2 Evaluation set

- `data/messages.json`: 15 messages with gold facts (reuse the scenarios and add more).
- `data/replies.csv` columns: `reply_id, message_id, lang_mix, reply_text, gold_labels (JSON map fact_id → status), author`.
- `eval/generate.py` expands hand-written templates into variants: swap numbers, spelling variants, word order, dropped facts and negation flips. Label them automatically from the template, and **keep generated rows clearly marked `synthetic=true`** separate from hand-written ones. Target 500+ labeled fact checks in total.
- Leave clear instructions in the README for teammates to add real hand-written replies in their own languages.
- `eval/run_baseline.py`: send message + gold fact list + reply to Gemini asking for a per-fact status in strict JSON. Run each item **5 times** to measure consistency. Cache responses to disk. Skip gracefully without a key.
- `eval/metrics.py`: fact-level accuracy, false "understood" rate (gold ∈ {wrong, missing, negated} but predicted understood), per-language and per-type breakdowns, confusion matrix, baseline consistency. Write to `eval/results/latest.json`.
- **Report results honestly,** including categories where the baseline beats us.

## 8. README.md (comprehensive; judges read this)

Sections:
1. Title, one-line pitch, badges.
2. Demo video link placeholder and screenshots/GIFs placeholders.
3. **The problem statement** and **how we read it**: the three workshop questions (what we crossed out: translation; the different moment: the response; who else: the sender).
4. The evidence, with the links from §0.
5. How it works, with a Mermaid architecture diagram and the pipeline.
6. **Why this is not an AI wrapper:** the principles in §1, the wrapper test, and what we built ourselves.
7. Features list.
8. Tech stack table.
9. Evaluation: methodology and a results table auto-filled from `eval/results/latest.json` by a script `eval/update_readme.py`.
10. Setup:
    - prerequisites;
    - `.env` variables;
    - `make dev`;
    - docker-compose;
    - running tests;
    - running the eval;
    - deploying (web on Vercel, API on Render/Railway/Fly).
11. Project structure.
12. Limitations and ethics:
    - not medical advice; the sender decides;
    - lexicon coverage;
    - synthetic eval data;
    - privacy: audio is not stored;
    - closest competitor, and how we differ.
13. Roadmap.
14. Team.

## 9. Demo video script (`docs/demo-script.md`, ≤ 2 minutes)

- **0:00–0:15:** The hook. "19% of answers about prescription labels are wrong, and teach-back fixes most of it, but the research excluded people with language barriers. In the UAE, that's millions." Show the landing hero animation.
- **0:15–0:45:** A pharmacist composes the scenario 1 message → facts appear → confirm → QR/link.
- **0:45–1:10:** On a phone, the reader page. Record a real Manglish voice reply with "oru week" and no rash warning.
- **1:10–1:35:** The sender dashboard updates live. Fact cards resolve; duration shows **wrong** with its reason; the warning is **missing**; hover shows the evidence spans. Draft the follow-up.
- **1:35–1:50:** Flip the wrapper-test toggle off; it still works. Flash the eval page: the false-"understood" rate, ours vs the baseline.
- **1:50–2:00:** The one-liner close and repo link.

Also add a `/demo` route or a `?demo=1` flag that pre-seeds data and shows "Simulate reply" presets, so the video can be recorded reliably even if STT is slow.

## 10. Execution order (commit after each; don't skip tests)

1. **Scaffold:** monorepo, Makefile, docker-compose, `.env.example`, empty README skeleton, `DECISIONS.md`.
2. **Engine core:** schema, normalize (with offsets), lexicon loader + seed lexicon, matcher, numeric slots (dose, duration), compare, `check_reply`. Tests for numbers pass.
3. **Engine complete:** frequency, timing, date, amount, condition, negation, confidence/unclear, evidence spans, optional fallback. All §4.6 tests pass. Generate `LEXICON_REVIEW.md`.
4. **API:** DB models, all routes, regex extractor, LLM extractor (optional), STT interface (Sarvam behind a flag, per its current docs), SSE, follow-up drafts, seed endpoint. API tests pass.
5. **Web foundation:** design tokens, theme, fonts, layout, nav, shared components, API client.
6. **Core flow pages:** composer → share → reader page (text first, then voice) → results with live SSE, highlights and animations.
7. **Landing page** with the animated hero and playground; **How it works** with the inspector and wrapper-test toggle.
8. **Eval pipeline:** generator, engine runner, baseline runner, metrics, eval page.
9. **Demo mode, polish pass** (motion, empty/error states, responsiveness, accessibility, reduced motion), the README auto-fill script, `docs/demo-script.md`.
10. **Final check:**
    - fresh clone → `make dev` works;
    - `make test` green;
    - `make eval` produces results;
    - the full demo flow works with `LLM_ENABLED=false` and no STT key.
    - Print a checklist of anything I (the human) must do: API keys, lexicon verification by native speakers, recording real replies, deploying, recording the video.

## 11. Things you must NOT do

- Don't add translation of messages or replies, a chatbot that talks to the reader, or any "score" shown to the reader.
- Don't let an LLM decide numeric, date, duration or negation outcomes.
- Don't fabricate evaluation numbers, citations or lexicon entries you're unsure of.
- Don't hard-code API keys; never commit `.env`.
- Don't block on missing API keys: every optional service degrades gracefully.
