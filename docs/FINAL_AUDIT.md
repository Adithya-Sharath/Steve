# Final audit

Run by `python scripts/final_audit.py` at 2026-09-26 17:02 UTC on branch `decode` at commit `8125528` (full run).

**Result: RED** (11 of 19 checks passed). `decode` is merged into `main` and tagged `v2.0.0` only when this is green.

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | engine tests | PASS | 579 passed |
| 2 | api tests | PASS | 438 passed |
| 3 | tools tests (speech-to-text tooling, no network) | PASS | 119 passed |
| 4 | ruff check engine api eval tools scripts | PASS | All checks passed! |
| 5 | openapi.json matches the running app | PASS | openapi.json is up to date |
| 6 | docs/API.md matches the running app (its JSON examples are real) | PASS | docs/API.md is up to date |
| 7 | web lint | **FAIL** | ✖ 1 problem (1 error, 0 warnings) |
| 8 | web | **FAIL** | crashed: UnicodeEncodeError: 'charmap' codec can't encode character '\u2716' in position 0: character maps to <undefined> |
| 9 | Check-mode evaluation reruns keyless and reproduces the committed numbers | **FAIL** | CHANGED: M eval/results/latest.json |
| 10 | Decode scorer runs on the frozen v2 set (current engine, contaminated label) | PASS | false alarm 1.4% of 144 |
| 11 | secrets scan of the working tree (key patterns) | **FAIL** | REVIEW: api/tests/test_translate.py, engine/tests/test_decode_cards.py, error, fatal, usage |
| 12 | the exact values in the local .env files are not in any tracked file | **FAIL** | FOUND IN TREE |
| 13 | secrets | **FAIL** | crashed: IndexError: list index out of range |
| 14 | `grep -ri samjha`: only the allowed historical hits | **FAIL** | REVIEW: api/app/services/followup.py, docs/README.md |
| 15 | dignity-word scan of every Decode user-facing string (files) | **FAIL** | REVIEW: api\app\services\translate.py:172: wrong; api\app\services\translate.py:377: wrong; api\app\services\translate.py:403: wrong; engine\steve_engine\decode\safety.py:2: wrong; copy_review.md:41: wrong; copy_review.md:41: incorrect |
| 16 | dignity tests over live API and WhatsApp responses (every field, all languages) | PASS | 4 passed |
| 17 | no log call in the Decode, translation or WhatsApp code takes text, a transcript, audio or a phone number | PASS | 9 files reviewed |
| 18 | no Decode code path writes a file or a database row with audio or message text (the only row is the WhatsApp hash, language and counters) | PASS | no file writes; the one database write is WorkerPref (hash, language, counters) |
| 19 | tests that capture logs, dump the database and forbid disk spooling of uploads | PASS | 12 passed |

## What the audit does not cover

* **Real-world validation.** No real workers, voice notes or messages were involved; every accuracy number is from public read speech or synthetic, author-written data (see the README and D42, D44, D49).
* **Live WhatsApp.** No WhatsApp message was ever sent; the flow was tested with mocked Twilio calls.
* **Docker.** The API image had not been built when this audit ran (Docker Desktop was off); `docs/DEPLOY.md` says so, and the first Render build is the first real build.
* **Independent security review.** None. The secrets scans look for key-shaped strings and for the exact values in the local `.env` files; a secret in another shape would not be found.
* **Native-speaker and legal review.** Every accent rule, glossary entry, word list and piece of copy is `verified: false` (see `ACCENT_REVIEW.md`, `GLOSSARY_REVIEW.md`, `copy_review.md`).

## Post-deploy smoke test

_Not run yet: it needs the live URLs from the owner (see `docs/DEPLOY.md`, step 5). This section is filled in after that run._
