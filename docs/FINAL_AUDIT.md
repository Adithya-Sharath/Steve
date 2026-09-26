# Final audit

Run by `python scripts/final_audit.py` at 2026-09-26 17:12 UTC on branch `decode` at commit `633ea2c` (full run).

**Result: GREEN** (25 of 25 checks passed). `decode` is merged into `main` and tagged `v2.0.0` only when this is green.

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | engine tests | PASS | 579 passed |
| 2 | api tests | PASS | 438 passed |
| 3 | tools tests (speech-to-text tooling, no network) | PASS | 119 passed |
| 4 | ruff check engine api eval tools scripts | PASS | All checks passed! |
| 5 | openapi.json matches the running app | PASS | openapi.json is up to date |
| 6 | docs/API.md matches the running app (its JSON examples are real) | PASS | docs/API.md is up to date |
| 7 | web lint | PASS | clean |
| 8 | web tsc --noEmit | PASS | clean |
| 9 | TypeScript client type-checks (strict) | PASS | clean |
| 10 | web production build | PASS | compiled |
| 11 | browser flows (Check mode, Listen + Paste + inspector + eval demo, TypeScript client) on the production build | PASS | 3/3 scripts passed, 128 checks |
| 12 | Check-mode evaluation reruns keyless and reproduces the committed numbers (only the timestamp differs) | PASS | identical |
| 13 | Decode scorer runs on the frozen v2 set (current engine, contaminated label) | PASS | false alarm 1.4% of 144 |
| 14 | secrets scan of the working tree (key patterns) | PASS | no key-shaped strings |
| 15 | the exact values of the secret-named variables in the local .env files are not in any tracked file | PASS | 3 secret values checked (GEMINI_API_KEY, HF_TOKEN, SARVAM_API_KEY), none found |
| 16 | secrets scan of the full history (89 revisions, key patterns and the exact .env values) | PASS | nothing found |
| 17 | no .env file, database, log or audio file is tracked | PASS | none tracked |
| 18 | .env, web/.env.local and eval/.cache are git-ignored | PASS | .env web/.env.local eval/.cache |
| 19 | no L2-ARCTIC audio or derived text is committed | PASS | only tooling and our own reports of counts |
| 20 | `grep -ri samjha`: only the allowed historical hits | PASS | 10 files, all on the allow-list (decision log, the rename guard, the eval seed string, the legacy storage key) |
| 21 | dignity-word scan of every Decode user-facing string (files) | PASS | 29 files, no shaming words |
| 22 | dignity tests over live API and WhatsApp responses (every field, all languages) | PASS | 4 passed |
| 23 | no log call in the Decode, translation or WhatsApp code takes text, a transcript, audio or a phone number | PASS | 9 files reviewed |
| 24 | no Decode code path writes a file or a database row with audio or message text (the only row is the WhatsApp hash, language and counters) | PASS | no file writes; the one database write is WorkerPref (hash, language, counters) |
| 25 | tests that capture logs, dump the database and forbid disk spooling of uploads | PASS | 12 passed |

## What the audit does not cover

* **Real-world validation.** No real workers, voice notes or messages were involved; every accuracy number is from public read speech or synthetic, author-written data (see the README and D42, D44, D49).
* **Live WhatsApp.** No WhatsApp message was ever sent; the flow was tested with mocked Twilio calls.
* **Docker.** The API image had not been built when this audit ran (Docker Desktop was off); `docs/DEPLOY.md` says so, and the first Render build is the first real build.
* **Independent security review.** None. The secrets scans look for key-shaped strings and for the exact values in the local `.env` files; a secret in another shape would not be found.
* **Native-speaker and legal review.** Every accent rule, glossary entry, word list and piece of copy is `verified: false` (see `ACCENT_REVIEW.md`, `GLOSSARY_REVIEW.md`, `copy_review.md`).

## Post-deploy smoke test

_Not run yet: it needs the live URLs from the owner (see `docs/DEPLOY.md`, step 5). This section is filled in after that run._
