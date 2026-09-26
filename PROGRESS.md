# PROGRESS

State of the build. Numbers below were produced by the final check run (see "Verification"), not typed from memory.
Pushed to <https://github.com/Adithya-Sharath/Steve> (`main`, tag `v1.0.0`). The repo looked **private** to an unauthenticated request (404): make it public before judging. GitHub Actions status has not been observed from here.

## Phases (from `docs/build-prompt.md` §10)
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

## Numbers (2026-09-25 final run)
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
**D17** Docker `$PORT` · **D18** production screenshots · **D19** README-count bug + truncation bug found by the final checks · **D20** CLAUDE.md/PROGRESS.md · **D21–D24** UI polish · **D25** baseline run · **D26** LLM deadline/fallback + lite default · **D27** Gemini needs a >= 10 s deadline · **D28** rename to Steve · **D29** publish prep · **D30** admin-only LLM switch · **D31** TRUST_PROXY client IP · **D32** rate limits · **D33** daily spending caps · **D34** prompt hardening + validation · **D35** headers, body cap, generic 500, masked logs · **D27** Gemini needs a >= 10 s deadline.

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
