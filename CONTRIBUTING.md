# Contributing to Steve

Thanks for helping. The most valuable contributions are **real replies from real speakers** and **native-speaker review of the lexicon**; code comes third.

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
cd engine && pytest -q        # deterministic engine
cd ../api && pytest -q        # API
ruff check engine api eval    # Python lint
cd web && npm run lint && npx tsc --noEmit && npm run build
```

`make test`, `make lint` and `make eval` wrap the same commands (Windows without `make`: `scripts/test.ps1`, `scripts/eval.ps1`).

## The rules that matter

1. An LLM never decides whether a safety-critical fact (number, dose, date, negation) was understood. That is `engine/` code.
2. Everything must keep working with no API keys.
3. A false "understood" is the worst error. A new rule may move a result *away* from `understood`; moving toward it needs a test that proves it.
4. Never translate the message or the reply. Never show a score to the reader.
5. Do not invent lexicon words. If you are not sure of a word, leave it out.

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

## Change the engine safely

Every behavioural change needs a test. Then `make test`, `make eval`, read the new error cases, run `python eval/update_readme.py` (it refuses to write numbers if a suite is red), and add a **DECISIONS.md** entry (trigger, rule, trade-offs). Commit each fix separately.

## Pull requests

Keep them small, describe what changed and why, and confirm the checks above pass. CI runs the same commands on every push.
