# PROGRESS

State of the build. Numbers below were produced by check runs, not typed from memory.
`main` (tag `v1.0.0`) is the published Check-mode product. **Active work is on the `decode` branch** (Decode pivot, D36).
The tag `check-mode-v1` marks the teach-back product before the pivot. Do not merge `decode` into `main` until the owner says so.

## Decode pivot: checklist (branch `decode`)

Decode = an interpreter that helps immigrant workers in the UAE understand the English they actually hear
(mother-tongue-influenced pronunciation, local phrases), returning plain English, optionally translated and spoken.
Channels: WhatsApp, and in person ("Tap to listen"). Check mode stays as a secondary, fully working feature.

| # | Phase | Status |
|---|---|---|
| 0 | Safety net: tag `check-mode-v1`, branch `decode`, decision D36, this checklist, CLAUDE.md | **done** |
| 1 | STT reality test (first directional result on 25 L2-ARCTIC clips, D39): `tools/stt_compare/` (recordings are the owner's). Decides how the decoder works | tooling **done** (27 tests, nothing sent to any provider yet); **STOPPED at Checkpoint 1: waiting for "recordings ready"**. 4th source (L2-ARCTIC, D38/D39): 25 Arabic+Hindi spontaneous clips run through Sarvam `--quick` (50 calls): accent sounds come back as the canonical ones (about 100% "fixed", phone-level proxy, directional only; says nothing yet about real-word swaps like barking/parking). Word level (no new calls): 48 real-word swaps in 24 clips, Sarvam wrote the intended word 44 times and the heard word 0. Scripted split (sibling terms accepted): 1,199 Arabic+Hindi utterances, 476 real-word swaps in 389 utterances; **targeted run done (D40): 389 utterances, 476 real-word swaps, intended word 89.9%, heard word kept 4.8%, other 4.0%; 67 of 1,528 accent words (4.4%) became a different real word (50 change the word). Report `tools/stt_compare/report_l2arctic_scripted.md` (gitignored): owner to review before any Phase 2 code**. Svarah and Speech Accent Archive importers built (inspect only); Svarah needs the owner to accept its gated terms. WhatsApp voice notes (.ogg/.opus) supported |
| 2 | **Redesigned (D40), not started, waiting for the 389-utterance report.** Voice path: STT (Sarvam transcribe) -> glossary -> actions -> negation -> meaning-level sanity checks -> clarify -> translate/speak; sound-swap rules only as a safety net when a transcribed word fits the context poorly. Typed-text path (WhatsApp, spelled by ear): full sound-swap decoding (accent packs `ar`, `common`, then `hi`/`ml`/`tl`, candidates, context pick). Shared: UAE glossary, actions, negation, `DecodedCard`, 80+ tests. New risk: silent plausible-but-wrong STT corrections, mitigated by context checks on where/when/amount and clarifying questions | not started |
| 3 | Decode evaluation: 300+ items (30+ real), word-change precision/recall, action accuracy, **wrong-but-confident rate**, Gemini baseline | not started |
| 4 | Decode API: `POST /decode`, `/decode/clarify`, worker key, limits and budgets reused | not started |
| 5 | Translation and voice output (optional, graceful) | not started |
| 6 | `/listen` "Tap to listen" web screen, "say it back", other-person notice (EN + AR, native review), language picker | not started |
| 7 | WhatsApp adapter (Twilio sandbox first, seam for Meta Cloud API), numbered clarify replies, onboarding | not started |
| 8 | Product surface and docs: nav, landing, how-it-works, README, SECURITY, CONTRIBUTING, screenshots, CI, final checks | not started |

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
