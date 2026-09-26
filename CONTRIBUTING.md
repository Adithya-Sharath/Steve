# Contributing to Steve

Thanks for helping. The most valuable contributions are **real voice notes and messages from real workers** (Decode), **real replies from real speakers** (Check mode) and **native-speaker review** of the accent packs, the glossary, the copy and the lexicons; code comes third.

## Set up

```bash
python -m venv .venv          # Windows: py -3 -m venv .venv
source .venv/bin/activate     # Windows: .\.venv\Scripts\Activate.ps1
pip install -e "engine[dev]" -e "api[dev]"
cd web && npm install && cd ..
```

No API keys are needed for anything below. Read [CLAUDE.md](CLAUDE.md) (rules and gotchas) and [DECISIONS.md](DECISIONS.md) (why things are the way they are) first.

## Run the tests

```bash
cd engine && pytest -q        # deterministic engine (Check mode and Decode)
cd ../api && pytest -q        # API (Decode, translation, WhatsApp, Check mode)
pytest tools/stt_compare -q   # speech-to-text tooling (needs: pip install -r tools/requirements.txt)
ruff check engine api eval tools scripts   # Python lint
python scripts/export_openapi.py --check && python scripts/make_api_docs.py --check   # the public API contract
cd web && npm run lint && npx tsc --noEmit && npm run typecheck:client && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build
node e2e/run.mjs all          # browser flows: Check mode, Listen, the TypeScript client (needs `npx playwright install chromium` once)
```

`make test`, `make lint` and `make eval` wrap the same commands (Windows without `make`: `scripts/test.ps1`, `scripts/eval.ps1`).

## The rules that matter

1. An LLM never decides whether a safety-critical fact (number, dose, date, negation) was understood. That is `engine/` code.
2. Everything must keep working with no API keys.
3. A false "understood" is the worst error. A new rule may move a result *away* from `understood`; moving toward it needs a test that proves it.
4. Check mode never translates the message or the reply and never shows a score to the reader. Decode translates only the settled English card (never the original text), only as text, and only when every number survived; nothing anywhere says "wrong" or "bad English" about a speaker.
5. Do not invent lexicon words, glossary meanings or accent rules. If you are not sure, leave it out; every such entry is `verified: false` until a native speaker checks it.
6. Decode never rewrites a negation, a number, an amount or a named time silently: if two readings are close it asks a question. Audio and message text are never stored or logged.
7. The Decode API is a public contract: a change to a response shape needs a decision record, a regenerated `openapi.json` and `docs/API.md` (`python scripts/export_openapi.py`, `python scripts/make_api_docs.py`); tests fail until they agree.

## Add real replies (most useful)

1. Add rows to `data/replies.csv`: `reply_id, message_id, lang_mix, reply_text, gold_labels, author, synthetic` with `synthetic=false`.
2. `gold_labels` is JSON mapping each fact id (see `data/messages.json`) to `understood | wrong | missing | negated | unclear`, **as a human would judge it, not as the engine says**.
3. Write in your own language and spelling. Hard cases are the valuable ones: words outside the lexicon, questions, half-answers, typos.
4. Run `python eval/run_engine.py && python eval/metrics.py` and read the error cases. Fix the lexicon or the rules, **never the labels**.

## Add or fix a lexicon entry

Entries live in `engine/steve_engine/lexicon.yaml`; the header of that file documents every field and flag.

1. Add the headword with its category, value and common by-ear spellings. Mark non-English entries `verified: false` until a native speaker signs off ([LEXICON_REVIEW.md](LEXICON_REVIEW.md), regenerate with `python engine/tools/make_lexicon_review.py`).
2. If the word is also a common word in another language, flag it (`ambiguous`, `requires_near`, `adjacent_only`).
3. Add a test in `engine/tests/`. `test_no_sound_key_collisions_between_different_meanings` guards the lexicon: no spelling may be equally close to two meanings.

## Add a language

A language is a lexicon block plus test data, not a model. Add the block (number words, units, frequency and timing phrases, negators, suffix rules), a few messages' worth of replies to `data/replies.csv`, and scenario presets in `data/scenarios.json`. Then run the engine tests and `make eval`.

## Add an accent pack (Decode)

An accent pack is a YAML file of *sound swaps*: what a speaker with that mother tongue often says instead of an English sound, so the decoder can undo it.

1. Copy `engine/steve_engine/decode/accents/ar.yaml` to `<id>.yaml` (`id` = a short code). Each rule is `{heard, meant, weight, phones, note, verified: false}`: `heard` and `meant` are spellings (typed path), `phones` are ARPAbet symbols (voice path), `weight` is a prior between 0 and 1, and `note` is one neutral sentence about the sound ("Arabic has no /p/ sound (barking for parking)"). **Never write anything that judges the accent.**
2. Register the id in `PACK_IDS` (`engine/steve_engine/decode/accents.py`) and in `ACCENT_HINTS` (`api/app/schemas.py`, and the `Literal` on `DecodeIn.accent_hint`); add a label in `web/lib/languages.ts` if the reference UI should offer it.
3. Add tests (`engine/tests/test_decode_data.py`, `test_decode_phonetics.py`) and regenerate the review sheet: `python engine/tools/make_accent_review.py`. Regenerate the API contract (`python scripts/export_openapi.py`, `python scripts/make_api_docs.py`).
4. **Measure on a set you did not tune on.** Add rows to a NEW evaluation set (never edit `eval_v1.csv` or `eval_v2.csv`; they are frozen) and commit it before its first scoring run (`eval/decode_eval.py --set <name>`). Report false alarms first.

## Add a glossary entry (Decode)

Entries live in `engine/steve_engine/decode/glossary.yaml`: `{phrase, variants, plain, literal, social_meaning, example, category, verified: false}`. `plain` is what the plain-English sentence says instead of the phrase; `literal` the word-for-word meaning; `social_meaning` how it is used, **neutral and respectful** (a phrase is explained, never judged; *inshallah* is not a lie). Categories `time` and `workplace` are explained but not substituted. Add the entry, a test in `engine/tests/test_decode_glossary_actions.py`, then `python engine/tools/make_glossary_review.py`. The word lists that say what a place, action or thing is live in `domain.yaml` (same rules).

## Add a reply language (Decode translation)

Languages are `en, ml, hi, ur, tl, bn`. To add one: (1) if Sarvam's `sarvam-translate:v1` covers it, add its BCP-47 code to `SARVAM_CODES` in `api/app/services/translate.py`; otherwise it goes to the guarded Gemini (`LANGUAGE_NAMES`); (2) add the code to `REPLY_LANGUAGES` and the `ReplyLanguage` `Literal` in `api/app/schemas.py`, `LANGUAGES` in `web/lib/languages.ts` (its own script, and `dir` for right-to-left) and `LANG_ORDER` / `LANG_NAMES` in `api/app/services/whatsapp.py`; (3) add its currency words to `CURRENCY_DRIFT` if you know them; (4) regenerate the API contract; (5) **ask a native speaker to test negated instructions** ("do not pay ...") before anyone relies on it: the number check cannot see a lost negation.

## Change the engine safely

Every behavioural change needs a test. Then `make test`, `make eval`, read the new error cases, run `python eval/update_readme.py` (it refuses to write numbers if a suite is red), and add a **DECISIONS.md** entry (trigger, rule, trade-offs). Commit each fix separately.

## Pull requests

Keep them small, describe what changed and why, and confirm the checks above pass. CI runs the same commands on every push.
