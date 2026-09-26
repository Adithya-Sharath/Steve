# CLAUDE.md — Steve

Instructions for Claude Code (and humans) working in this repo. Keep it short and true; update it when reality changes.
Read `DECISIONS.md` first (D1–D37: every non-obvious choice and why) and `PROGRESS.md` (what is done, what is not).

## What this is
**Steve is pivoting to Decode** (D36, branch `decode`): an interpreter that helps immigrant workers in the UAE understand the English they
actually hear: mother-tongue-influenced pronunciation ("barking" for "parking" because Arabic has no /p/) and local phrases ("yalla", "khalas",
"inshallah"). It returns plain English, optionally translated into the worker's language and spoken back, over WhatsApp and an in-person
"Tap to listen" screen. The plan is the phase checklist in `PROGRESS.md`.

**Check mode** (the original product, tag `check-mode-v1`, published on `main`) stays as a secondary feature and must keep working: a sender writes an
important message, confirms its key facts, the reader explains it back in their own words (Manglish / Hinglish / Arabizi / Taglish), and a
**deterministic engine** marks each fact `understood | wrong | missing | negated | unclear`. BitNBuild'26 hackathon project; the original brief is
`docs/build-prompt.md`.

**Next task:** Phase 1, the STT reality test (`tools/stt_compare/`). The owner records the audio; do not build the decoder (Phase 2) until the
report says whether speech-to-text keeps what was actually said or silently "fixes" it. Work on the `decode` branch; never push to `main` or force-push.

**Decode rules (in addition to the ones below):** deterministic rules first; an LLM is optional, guarded (`llm_guard.py`) and never the sole judge of a
where/when/amount; if two readings are close, ask a clarifying question instead of guessing; never call speech "wrong" or "bad English" and show no
scores; audio is never stored and phone numbers are hashed; every accent rule and glossary entry is `verified: false` until a native speaker reviews it;
never invent linguistic facts (leave them out); the full pipeline must work with zero API keys.

## Non-negotiable rules
1. **An LLM never decides a safety-critical fact.** Numbers, doses, frequencies, durations, dates, amounts and negations are decided
   by code in `engine/`. LLM (Gemini) may only suggest facts (the sender confirms) and power the eval baseline.
2. **Everything works with zero API keys** (`LLM_ENABLED=false`, no STT). Optional services must degrade gracefully.
3. **No translation** of messages or replies. Show the reader's words verbatim. Never show a score to the reader.
4. **A false "understood" is the worst error.** Low confidence, conflicts, concessives ("even if rash"), pasted messages and
   unreadable numbers must end in `unclear`/`missing`/`negated`, never `understood`. New rules may only move results *away* from `understood`
   unless a test proves otherwise.
5. **Do not fabricate** numbers, citations or lexicon words. If unsure of a word, leave it out. Non-English lexicon entries are
   `verified: false` until a native speaker signs off (`LEXICON_REVIEW.md`).
6. **Never commit `.env` or keys.** Never push to GitHub unless the user asks.

## Commands (`make` targets; on Windows without make use the equivalents)
| Task | make | Windows / direct |
|---|---|---|
| install | `make install` | `pip install -e "engine[dev]" -e "api[dev]"`; `cd web && npm install` |
| run all | `make dev` | `scripts/dev.ps1`, or `cd api && uvicorn app.main:app --reload --port 8000` + `cd web && npm run dev` |
| tests | `make test` | `scripts/test.ps1` (`cd engine && pytest -q`; `cd api && pytest -q`) |
| lint | `make lint` | `ruff check engine api eval`; `cd web && npm run lint && npm run typecheck` |
| eval | `make eval` | `scripts/eval.ps1` (generate -> run_engine -> run_baseline -> metrics -> update_readme) |
| STT reality test | - | `python tools/stt_compare/run.py` (plan only) / `--yes` (calls providers); `python -m pytest tools/stt_compare -q` |
| lexicon sheet | `make lexicon-review` | `python engine/tools/make_lexicon_review.py` |

## Layout
`engine/` pure Python (`steve_engine`: normalize, lexicon.yaml, matcher, slots, negation, compare, copycheck, check) ·
`api/` FastAPI + SQLModel/SQLite (`app/`: routes, services, auth, db) · `web/` Next.js 16 App Router (Tailwind v4, shadcn/ui on Base UI,
Framer Motion, TanStack Query) · `data/` scenarios.json (demo **and** regression tests), messages.json + replies.csv (eval gold) ·
`eval/` pipeline · `docs/` architecture, demo script, screenshots.

## How to change the engine safely
- Every behavioural change needs a **test** (`engine/tests/`). `data/scenarios.json` presets have hand-declared `expected` statuses and run as tests.
- Then: `make test`, `make eval`, read the new error cases, `python eval/update_readme.py` (also refreshes README test counts; it refuses if a suite is red),
  and add a **DECISIONS.md** entry (trigger, rule, trade-offs). Commit each fix separately.
- `engine/tests/test_slots_and_compare.py::test_no_sound_key_collisions_between_different_meanings` guards the lexicon: no by-ear spelling may be
  equally close to two meanings. Ambiguous words carry `ambiguous` / `requires_near` / `adjacent_only` flags; read the header of `lexicon.yaml`.
- Eval data: synthetic rows are regenerated; hand-written rows (`hw-*`, `ho-*`, teammates') live only in `data/replies.csv`. Fix the lexicon or rules, **never the labels**.
  The engine was developed while reading this data, so its numbers are development numbers (D10).

## API / auth
Sender endpoints need `X-Sender-Key: sk_<32+ chars>` (SSE stream may use `?key=`); the server stores only its SHA-256 hash (D16).
The global LLM switch needs `X-Admin-Key` = `ADMIN_KEY` (unset = 403 for all, D30). Client IP comes from `clientip.client_ip`, which trusts proxy headers only with `TRUST_PROXY=true` (D31).
Every limit is in `settings.py` and `.env.example`: rate limits (D32), daily caps (D33), LLM answer validation (D34), body cap/headers/500 (D35). In API tests limits are lifted in `conftest.py` and reset per test; add a test that sets them when you touch one.
Reader endpoints (`/r/{token}...`) are open by token. In API tests the `client` fixture is sender A, `other` is sender B, `anon` has no key.
Existing SQLite files are migrated in place by `db._ensure_columns()` (add new columns there).

## Web gotchas
- Next 16 / React 19 with the strict React-compiler ESLint rules: no `setState` in effects, no reassigning variables during render (see `components/*` for the patterns used).
- Engine offsets are Python **code points**; slice with `Array.from` (`lib/spans.ts`).
- Retake `docs/screenshots` only from a production build (`next build && next start`) so the dev badge never appears (D18).

## Environment gotchas seen so far
- Windows: no `make`; Docker Desktop may be off (the API image has never been built here; `docker compose config` validates only).
- When patching files with shell heredocs, `\n` inside Python string literals can turn into real newlines. Prefer the editor tools, and **assert that a replacement applied** (a silent no-op once left the README test counts stale, D19).
- Scripts that write `README.md`/data files must compute the new content *before* opening the file for writing.
