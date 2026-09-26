# PROGRESS

State of the build. Numbers below were produced by the final check run (see "Verification"), not typed from memory.
Everything is committed locally; **nothing has been pushed to GitHub.**

## Phases (from `docs/build-prompt.md` §10)
| # | Phase | Status |
|---|---|---|
| 1 | Scaffold (monorepo, Makefile, compose, env, DECISIONS) | done |
| 2–3 | Engine (lexicon, by-ear matcher, slots, negation, compare, confidence, evidence spans, optional fallback), `LEXICON_REVIEW.md` | done |
| 4 | API (routes, SQLite, extractor, STT interface, SSE, follow-up, seed) | done |
| 5–7 | Web (design system, landing + animated hero + playground, dashboard, composer, results with SSE, reader with voice, how-it-works, demo, eval page) | done |
| 8 | Eval pipeline (generator, engine runner, Gemini baseline, metrics, README updater) | done; **baseline never run** (no key) |
| 9 | Demo mode, polish, README, architecture, demo script | done |
| 10 | Final check + human checklist | done (below) |
| — | UI polish round (21st.dev MCP, 2 free downloads/day): **buttons with depth** (D21) and **landing stats bento + how-it-works timeline** (D22) done; **staggered fact-card resolve** (D23) and **reader record button** (D24) done | done |
| — | Follow-up round: negation typos, concessives, copy-paste, SMS shorthand, sender auth, Docker `$PORT`, production screenshots, this file | done (D12–D20) |

## Numbers (2026-09-25 final run)
- **Engine tests:** 275 passed, 1 skipped. **API tests:** 42 passed. `ruff`, `eslint`, `tsc` clean. Fresh-clone install + tests + eval + web build all pass.
- **Eval (development numbers, see D10):** 2,268 labelled fact checks over 561 replies (114 hand-written, 447 synthetic).
  Accuracy 96.9%. **False "understood": 0 of 921** not-understood facts (hand-written 0/69, held-out 0/41, synthetic 0/811).
  Hand-written 98.8%, held-out 89.1% (first blind run, before any fix: 87.4%), synthetic 97.3%. Read the caveats: denominators are small and the data is ours.
- **LLM baseline:** not run. `python eval/run_baseline.py` needs `GEMINI_API_KEY`; without it `/eval` and the README say "baseline not run".
- **Browser end-to-end (production build):** 16/16 checks pass (compose → confirm → reader reply → live SSE update → copy banner → follow-up → second browser locked out → demo).
- **Lighthouse (production build):** accessibility 100 on `/`, `/how-it-works`, `/app`, `/eval`, `/demo`, `/app/new`; best practices 96–100; performance 77–93.
- **Secret scan:** no keys in the working tree or any git revision; no `.env` exists.

## Decisions index (`DECISIONS.md`)
D1 repo/brief · D2 widened units/types · D3 code-point offsets · D4 claiming · D5 conflict⇒unclear · D6 words left out (partly superseded by D12) · D7 bare numbers ·
D8 embedding fallback off · D9 eval honesty · D10 eval history / held-out set · D11 safety rules from error analysis · **D12** SMS/typo negators + fuzzy negator match ·
**D13** concessive clauses · **D14** copy-paste detection (two deliberate deviations from the spec'd rule) · **D15** English shorthand · **D16** sender-key auth ·
**D17** Docker `$PORT` · **D18** production screenshots · **D19** README-count bug + truncation bug found by the final checks · **D20** CLAUDE.md/PROGRESS.md.

## Known gaps / risks (honest list)
- Lexicon: ~300 headwords, 5 languages, all non-English entries **unverified**; numbers above ten only as digits; unknown words give `missing`/`unclear`, never a guess.
- Residual false-"understood" risk: a negation word we cannot recognise even fuzzily; a concessive phrased without any known marker; facts whose wording is too close to the message to look "copied" but which were parroted.
- Concessive + `only after N days` stays `unclear` (cannot be read as "don't stop"). Copy detection needs the reply to be long *and* in the same order as the message.
- Sender key lives in one browser (no recovery/rotation); the LLM toggle is global; old rows without an owner are unreadable.
- Docker images were **never built** (Docker Desktop was off); compose file only validated. `make` is not installed on this machine (targets were run as direct commands).
- Voice: Sarvam covers Malayalam/Hindi/English only, and was tested with a **mocked** HTTP call, never against the live service.
- Gemini default model id (`gemini-3.8-flash`) came from the Gemini docs page but was never called; verify it.
- Held-out data is no longer blind; there is no real native-speaker data yet.

## Human checklist (things only you can do)
1. Put keys in `.env` (all optional): `GEMINI_API_KEY`, `SARVAM_API_KEY`. **Any key pasted into a chat should be rotated after the hackathon.** Then run the baseline in small steps first
   (`python eval/run_baseline.py --runs 3 --synthetic-sample 40`), mind the free-tier limits, and never send real patient data.
2. Native speakers: review `LEXICON_REVIEW.md`; add real replies to `data/replies.csv` (README "Adding real replies").
3. Test voice on a real phone over HTTPS with a real Sarvam key.
4. Build and run the Docker images; deploy web (Vercel) and API (Render/Railway/Fly). Set `LLM_ENABLED` in the environment on a public deployment.
5. Record the video from `docs/demo-script.md`; add video/live URLs, team names and a licence to the README.
6. Decide when to `git push` (nothing has been pushed).

## Next steps (suggested order)
Native-speaker lexicon review → real blind test set → run the baseline → deploy → calibrate/enable the embedding fallback → WhatsApp Business delivery → Arabic/Tagalog voice.
