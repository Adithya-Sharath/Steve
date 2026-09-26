# PROGRESS

State of the build. Numbers below were produced by check runs, not typed from memory.
`main` (tag `v1.0.0`) is the published Check-mode product. **Active work is on the `decode` branch** (Decode pivot, D36).
The tag `check-mode-v1` marks the teach-back product before the pivot. Do not merge `decode` into `main` until the owner says so.

## Decode pivot: checklist (branch `decode`)

Decode = an interpreter that helps immigrant workers in the UAE understand the English they actually hear
(mother-tongue-influenced pronunciation, local phrases), returning plain English, optionally translated (text only: no text-to-speech anywhere).
Channels: WhatsApp, and in person ("Tap to listen"). Check mode stays as a secondary, fully working feature.

| # | Phase | Status |
|---|---|---|
| 0 | Safety net: tag `check-mode-v1`, branch `decode`, decision D36, this checklist, CLAUDE.md | **done** |
| 1 | STT reality test (first directional result on 25 L2-ARCTIC clips, D39): `tools/stt_compare/` (recordings are the owner's). Decides how the decoder works | tooling **done** (27 tests, nothing sent to any provider yet); **STOPPED at Checkpoint 1: waiting for "recordings ready"**. 4th source (L2-ARCTIC, D38/D39): 25 Arabic+Hindi spontaneous clips run through Sarvam `--quick` (50 calls): accent sounds come back as the canonical ones (about 100% "fixed", phone-level proxy, directional only; says nothing yet about real-word swaps like barking/parking). Word level (no new calls): 48 real-word swaps in 24 clips, Sarvam wrote the intended word 44 times and the heard word 0. Scripted split (sibling terms accepted): 1,199 Arabic+Hindi utterances, 476 real-word swaps in 389 utterances; **targeted run done (D40): 389 utterances, 476 real-word swaps, intended word 89.9%, heard word kept 4.8%, other 4.0%; 67 of 1,528 accent words (4.4%) became a different real word (50 change the word). Report `tools/stt_compare/report_l2arctic_scripted.md` (gitignored): owner to review before any Phase 2 code**. Svarah and Speech Accent Archive importers built (inspect only); Svarah needs the owner to accept its gated terms. WhatsApp voice notes (.ogg/.opus) supported |
| 2 | Decoder (D40/D41/D43), **built, at Checkpoint 2 (waiting for the owner)**. Voice path: STT -> glossary -> safety net on critical spans -> actions -> clarify; typed path: glossary -> full sound-swap decoding -> actions -> clarify. 61-entry glossary, 5 accent packs, 7-category domain list (all `verified: false`), `DecodedCard`, 247 decode tests (engine 522 passed, api 228, tools 119). Synthetic (tuned on): voice catch 66.5% / false alarm 0.0%, typed 57/58 / false alarm 0.0%. Held-out L2-ARCTIC: catch 0/72 (literary words outside the critical slots), false alarm 0.3% (12/3,635). Optional masked LM not built | **Checkpoint 2** |
| 3 | Decode evaluation (D44): frozen synthetic sets `eval_v1` (458 rows) and `eval_v2` (245 rows, written after the fixes), `eval/decode_eval.py`, reports in `eval/results/`. Headline (fresh v2 first run): **false alarm 1.4% (2/144, questions only)**; typed by ear in-pack 94.0% exact / out-of-pack 0% decoded (left as typed); extraction where 91.7% / when 87.1% / what 95.0% / how much 100%. Voice-net catch only with its label (synthetic, author-written, tuned on it: 66.5%; held-out L2-ARCTIC 0/72, outside critical slots). Optional accented-TTS test and Gemini baseline **not run: awaiting the owner** | **done (Checkpoint 3)**, awaiting review |
| 4 | Decode API (D45): `POST /decode` (JSON text or multipart audio), `POST /decode/clarify`, `GET /decode/health`; worker key `X-Worker-Key`, in-memory clarify state (10 min), per-IP/per-worker limits, audio caps, fake-STT tests, no text or audio in logs | **done** (50 API tests) |
| 5 | Translation, **text only, no TTS anywhere** (D46): Sarvam `sarvam-translate:v1` for ml/hi/ur/bn, guarded Gemini for tl and as fallback, protected numbers/times/places/amounts, exact-match number check (a failing translation is never shown), cache, budgets; one live Sarvam call and one live Gemini call succeeded | **done** (57 tests; API suite 334) |
| 6 | **Full, demo-grade** `/listen` (D50 supersedes D47's reference-UI scope): Listen + Paste, example chips from `GET /decode/examples`, card, clarify buttons, language picker, say-it-back, notice EN + AR, RTL, cold-start retry, mic-denied and voice-off fallbacks, 375 px, 44 px targets; plus the public API contract (`docs/API.md`, `openapi.json`, TS client, CORS); browser flows `web/e2e/` | **in progress (D50 rework)** |
| 7 | WhatsApp, text replies only (D48): Twilio sandbox provider behind a seam, signed webhook, voice notes, images, onboarding, numbered questions, EN / LANGUAGE / HELP, splitting, per-number limits, hashed numbers; 63 mocked tests, **no live message sent**; `docs/whatsapp-setup.md` for the owner | **done** (API suite 417) |
| 8 | `/` = short intro + "Try it"; How-it-works inspector (Decode); Decode tab on the Evaluation page; Check mode secondary in the nav; Gemini baseline on v2; README (Decode primary); SECURITY, CONTRIBUTING, screenshots, CI; final audit `docs/FINAL_AUDIT.md`; merge to `main` and tag `v2.0.0` only if the audit is fully green | in progress |

## Phases 4 to 8: run plan (owner prompt `CLAUDE_CODE_PROMPT_Steve_Phases_4_to_8.md`; scope: text output only, NO text-to-speech anywhere)

Phase gate (every phase): engine + tools + api tests, `ruff check engine api eval tools`, web lint + `tsc --noEmit` + production build, the Check-mode browser flow
(`cd web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build && node e2e/run.mjs check`), the new flow tests of the phase. `node e2e/run.mjs` starts a mock Sarvam, the API and the production web build.

**Phase 4 plan.** Files: `engine/.../decoder.py` (`resolved` answers), `api/app/{settings,auth,ratelimit,schemas}.py`, `routes/decode.py`, `services/{audio,decode_sessions,decode_flow,decode_translation,stt}.py`, `tests/test_decode_api.py`, e2e stack (`web/e2e/`). Done when: text card equals `decode()`; audio through a fake STT; size/duration caps; STT off gives a typing note; clarify resolves / expires / rejects another worker; limits and budgets; no text or audio in logs; dignity scan; all gates green.

**Phase 5 plan (done).** `services/translate.py`, `decode_translation.py` seam, `TRANSLATE_DAILY_CAP`, `tests/test_translate.py`. Done criteria met: fake translator, placeholder round trip, number-mismatch rejection (3 -> 8), fallbacks, budget handling, one live Sarvam + one live Gemini call logged in D46.

**Phase 6 plan.** Web `/listen` (Listen + Paste tabs), worker key + language picker in `lib/`, card UI with clarify buttons and translation toggle, "say it back" as large text, EN + AR other-person notice (`copy_review.md`), RTL, 56 px targets, `web/e2e/listen.mjs` (fake mic, mock Sarvam) + axe + Lighthouse >= 95. Done when all Phase 6 tests and the phase gate pass.

**Phase 6 plan (revised by D47).** Reference `/listen` only; public contract (`docs/API.md`, `openapi.json`, TS client, `/decode/examples`, CORS); browser flows `listen` and `client`. Done: see the table.

**Phase 7 plan.** `services/messaging/` (provider interface, Twilio sandbox first, seam for Meta), `POST /whatsapp/webhook` (signature verified, text + voice + image), hashed numbers (`WORKER_HASH_SECRET`), in-memory numbered clarify state, onboarding and commands, per-number limits, `tests/test_whatsapp.py` with mocked Twilio, `docs/whatsapp-setup.md`. No live message is sent in this run.

Typed-text truth file: `tools/stt_compare/typed_truth.csv` (`text_as_typed, intended_meaning, accent, source, notes`; the owner supplies WhatsApp screenshots/examples; anonymised; validator rejects phone numbers, e-mails and links).

Checkpoints: 0 (plan and tag: this file) · 1 (STOP and wait for "recordings ready") · 2 (decoder tests and 10 example cards) · 3 (metrics: engine vs baseline) · 6 (/listen) · 7 (WhatsApp steps) · 8 (final report, then wait before merging).

Rules that do not change: deterministic rules first; an LLM is optional, guarded (`llm_guard.py`) and never the sole judge of a where/when/amount;
uncertainty becomes a clarifying question, never a silent guess; dignity (never "wrong" or "bad English", no scores); audio never stored, phone numbers hashed;
every accent rule and glossary entry is `verified: false` until a native speaker reviews it; the full decode pipeline works with zero keys.

**Evidence gap (owner, 2026-09-26):** no real recordings or real typed messages will be provided for now. Real-world validation (real voice notes, real typed messages) is missing; all current numbers come from public read speech (L2-ARCTIC) plus synthetic data. To narrow the gap the owner asked for a WhatsApp-like simulation of the 389 scripted clips (noise, Opus, phone quality; D42), which is still a simulation.

## Check mode (teach-back): what was built (kept, still working)
Phases from `docs/build-prompt.md` §10:

| # | Phase | Status |
|---|---|---|
| 1 | Scaffold (monorepo, Makefile, compose, env, DECISIONS) | done |
| 2–3 | Engine (lexicon, by-ear matcher, slots, negation, compare, confidence, evidence spans, optional fallback), `LEXICON_REVIEW.md` | done |
| 4 | API (routes, SQLite, extractor, STT interface, SSE, follow-up, seed) | done |
| 5–7 | Web (design system, landing + animated hero + playground, dashboard, composer, results with SSE, reader with voice, how-it-works, demo, eval page) | done |
| 8 | Eval pipeline (generator, engine runner, Gemini baseline, metrics, README updater) | done; baseline run on a lite model (D25) |
| 9 | Demo mode, polish, README, architecture, demo script | done |
| 10 | Final check + human checklist | done (below) |
| — | UI polish round (21st.dev MCP, 2 free downloads/day; all four targets committed, D21-D24): **buttons with depth** (D21) and **landing stats bento + how-it-works timeline** (D22) done; **staggered fact-card resolve** (D23) and **reader record button** (D24) done | done |
| — | LLM safety net (D26): **10 s deadline + automatic fallback to the built-in extractor + 60 s cooldown**; default `GEMINI_MODEL` is now `gemini-3.1-flash-lite` (settings, `.env.example`, README, baseline runner) | done |
| — | Real-phone test through Cloudflare tunnels worked (voice via Sarvam). It exposed a D26 bug: Gemini rejects deadlines under 10 s, so "Find key facts" always fell back. **D27:** SDK deadline never below 10 s, default timeout 10 s, 503 = short cooldown, provider error message logged (key redacted) | done |
| — | **Rename to Steve (D28)**: package, env vars, DB, Docker, UI, sender-key storage migration; keyless eval numbers identical; screenshots retaken | done |
| — | **Publish prep (D29)**: MIT licence, CONTRIBUTING, SECURITY, GitHub templates, CI (engine+api on Python 3.11, web on Node 22, verified in a fresh clone), judge-first README, secret scan of tree and full history | done; pushed |
| — | **API/AI security layer (D30-D35, local commits, not pushed):** admin-only global LLM switch (`ADMIN_KEY`, hidden in the web unless the key is stored via `/admin`), `TRUST_PROXY` real client IP, rate limits (one reusable sliding-window dependency), daily Gemini/Sarvam caps with fallbacks, Gemini prompt hardening + server-side validation, security headers / 5 MB body cap / generic 500 / masked logs, docs | done |
| — | Follow-up round: negation typos, concessives, copy-paste, SMS shorthand, sender auth, Docker `$PORT`, production screenshots, this file | done (D12–D20) |

## Numbers, Check mode (2026-09-25 final run; API tests since updated)
- **Engine tests:** 275 passed, 1 skipped. **API tests:** 228 passed (incl. 20 for D26/D27, 5 for the rename guard D28, and 161 added for the security layer D30-D35, 67 before it). `ruff`, `eslint`, `tsc` clean. Fresh-clone install + tests + eval + web build all pass.
- **Eval (development numbers, see D10):** 2,268 labelled fact checks over 561 replies (114 hand-written, 447 synthetic).
  Accuracy 96.9%. **False "understood": 0 of 921** not-understood facts (hand-written 0/69, held-out 0/41, synthetic 0/811).
  Hand-written 98.8%, held-out 89.1% (first blind run, before any fix: 87.4%), synthetic 97.3%. Read the caveats: denominators are small and the data is ours.
- **LLM baseline (run, D25):** `gemini-3.1-flash-lite`, 154 replies x 3 runs, 665 fact checks. Baseline accuracy 94.6% vs our 95.9% on the same rows; **false "understood" 11/180 (6.1%) vs 0/180**. Excluding the 14 pasted-message rows (our rule, not in its prompt) the **baseline is more accurate on plain facts: 96.6% vs 95.9%**. Baseline was perfectly self-consistent, so consistency is not our advantage. The comparison favours us (engine tuned on this data). Free-tier quotas on the larger models (about 20 requests/day) forced the lite model.
- **Browser end-to-end (production build):** 16/16 checks pass (compose → confirm → reader reply → live SSE update → copy banner → follow-up → second browser locked out → demo).
- **Lighthouse (production build):** accessibility 100 on `/`, `/how-it-works`, `/app`, `/eval`, `/demo`, `/app/new`; best practices 96–100; performance 77–93.
- **Secret scan (re-run for D29):** 32 revisions and the working tree scanned for key patterns and for the exact values in the local `.env`: nothing found. `.env`, `web/.env.local`, `*.db`, `*.log`, `.venv`, `node_modules`, `.next`, `eval/.cache`, cloudflared binaries and `.mcp.json` are gitignored and untracked; no tracked file is over 5 MB.
- **CI dry run:** the exact CI commands passed in a fresh clone with Python 3.11 (`ruff` 0.16.9, 275 engine + 67 API tests) and Node 22 (`npm ci`, eslint, `tsc`, `next build`). The GitHub run itself is not yet observed.

## Decisions index (`DECISIONS.md`)
D1 repo/brief · D2 widened units/types · D3 code-point offsets · D4 claiming · D5 conflict⇒unclear · D6 words left out (partly superseded by D12) · D7 bare numbers ·
D8 embedding fallback off · D9 eval honesty · D10 eval history / held-out set · D11 safety rules from error analysis · **D12** SMS/typo negators + fuzzy negator match ·
**D13** concessive clauses · **D14** copy-paste detection (two deliberate deviations from the spec'd rule) · **D15** English shorthand · **D16** sender-key auth ·
**D17** Docker `$PORT` · **D18** production screenshots · **D19** README-count bug + truncation bug found by the final checks · **D20** CLAUDE.md/PROGRESS.md · **D21–D24** UI polish · **D25** baseline run · **D26** LLM deadline/fallback + lite default · **D27** Gemini needs a >= 10 s deadline · **D28** rename to Steve · **D29** publish prep · **D30** admin-only LLM switch · **D31** TRUST_PROXY client IP · **D32** rate limits · **D33** daily spending caps · **D34** prompt hardening + validation · **D35** headers, body cap, generic 500, masked logs · **D36** Decode pivot · **D37** STT reality-test tooling · **D38** L2-ARCTIC 4th source (CC-BY-NC) · **D39** first STT result, Svarah/SAA importers, WhatsApp audio · **D40** STT normalises accent words: Phase 2 redesigned (voice vs typed paths) · **D41** Phase 2 go-ahead specifics · **D42** WhatsApp-like simulation (clean 89.9% -> noisy 87.4% intended; wrong-real-word 4.4% -> 6.9%) and the evidence gap · **D27** Gemini needs a >= 10 s deadline.

## Known gaps / risks (honest list)
- Lexicon: ~300 headwords, 5 languages, all non-English entries **unverified**; numbers above ten only as digits; unknown words give `missing`/`unclear`, never a guess.
- Residual false-"understood" risk: a negation word we cannot recognise even fuzzily; a concessive phrased without any known marker; facts whose wording is too close to the message to look "copied" but which were parroted.
- Concessive + `only after N days` stays `unclear` (cannot be read as "don't stop"). Copy detection needs the reply to be long *and* in the same order as the message.
- Sender key lives in one browser (no recovery/rotation); old rows without an owner are unreadable. The LLM switch is global but now admin-only; the admin key sits in the operator browser's `localStorage`.
- Security layer limits: rate limits, daily caps and the body cap are per API process (restart or several workers weaken them) and are a brake, not DDoS protection or billing; set provider-side spending limits too. Validation of Gemini output cannot tell a plausible wrong fact from a right one (the sender confirms). A reverse proxy's own access log keeps `?key=` URLs. With `TRUST_PROXY=false` behind a proxy all visitors share one rate-limit bucket.
- Docker images were **never built** (Docker Desktop was off); compose file only validated. `make` is not installed on this machine (targets were run as direct commands).
- Voice: Sarvam covers Malayalam/Hindi/English only. Automated tests use a **mocked** HTTP call; the live service was tried by hand on a real iPhone through Cloudflare tunnels (2026-09-26, reported by the team, not recorded here).
- Gemini `gemini-3.8-flash` is a valid id but the free tier allows about 20 requests/day; the default is now the lite model and every LLM call has a 10 s deadline with fallback (D26, D27). A local `.env` that sets `GEMINI_MODEL=gemini-3.8-flash` explicitly still overrides the default. Sarvam and voice were not exercised against the live service.
- Held-out data is no longer blind; there is no real native-speaker data yet.

## Human checklist (things only you can do)
0. **Deploying?** Set `ADMIN_KEY` (32+ random chars) if you want the LLM switch, `TRUST_PROXY=true` on Render/behind a tunnel (see `.env.example`), and spending limits at Google/Sarvam. Demo-tunnel stack: `ADMIN_KEY=...` and `TRUST_PROXY=true` in `.env`, paste the key once on `/admin`.
1. Put keys in `.env` (all optional): `GEMINI_API_KEY`, `SARVAM_API_KEY`. **Any key pasted into a chat should be rotated after the hackathon.** Then run the baseline in small steps first
   (`python eval/run_baseline.py --runs 3 --synthetic-sample 40`), mind the free-tier limits, and never send real patient data.
2. Native speakers: review `LEXICON_REVIEW.md`; add real replies to `data/replies.csv` (README "Adding real replies").
3. ~~Test voice on a real phone~~ done on an iPhone over HTTPS (tunnels). Repeat it on the final deployed URLs.
4. Build and run the Docker images; deploy web (Vercel) and API (Render/Railway/Fly). Set `LLM_ENABLED` in the environment on a public deployment.
5. Record the video from `docs/demo-script.md`; replace `VIDEO_LINK_HERE` and the `NAME_n — role` lines in the README (licence: done, MIT).
6. ~~Rename the repo and push~~ done. Make the repository public, set the description and topics, publish the v1.0.0 release, and check the Actions tab is green.

## Next steps (suggested order)
Native-speaker lexicon review → real blind test set → run the baseline → deploy → calibrate/enable the embedding fallback → WhatsApp Business delivery → Arabic/Tagalog voice.
