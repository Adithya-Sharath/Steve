# Decisions

Ambiguities in the build brief and how we resolved them. Newest at the bottom.

## D1 — Repo lives in a fresh clone, brief kept in `docs/`
The brief (`docs/build-prompt.md`) is copied in for provenance. The repo is `Adithya-Sharath/Samjha`.

## D2 — Facts model is slightly generalised beyond medicine
The brief's four scenarios (construction site, visa/HR, school circular) contain facts the medical-flavoured
`FactType` list can't express literally. We keep the seven fact types and widen only their *units*:

| Type | Extension | Why |
|---|---|---|
| `dose` | unit may also be `bottle`, `photo`, `form`, `copy` (not only tablet/ml/puff/drop/capsule/spoon) | "1 bottle of water", "2 photos" |
| `duration` | `unit` may be `day` (default, value in days), `hour` or `minute` (value in that unit) | "15-minute break" |
| `date` | value may also be a clock time `"12:30"` (besides ISO date / weekday) | "break at 12:30" |
| `condition` | action may also be `avoid` (the trigger word is the thing to avoid, e.g. *travel*) | "Do not travel until your visa is stamped" |

Nothing else about the schema changes. All numeric/date/negation decisions remain deterministic code.

## D3 — Offsets are Python code points
`Span.start/end` index the original reply as a Python `str` (code points). The web client splits with
`Array.from(text)` so emoji (astral code points) highlight correctly.

## D4 — "Claiming" between facts of the same type
Messages often carry two facts of the same type (two dates: trip Monday, deadline Friday). A heard value that
equals *another* fact's expected value is "claimed" by that fact and is never used as evidence that *this* fact
was heard wrong. So replying only "friday" leaves the "Monday" fact `missing`, not `wrong`.

## D5 — Conflict ⇒ unclear
If a reply contains the expected value **and** a conflicting unclaimed value for the same slot
("2 tablets … 3 tablets"), the result is `unclear`, never `understood`.

## D6 — Words deliberately left out of the lexicon
Hindi/Tagalog `na` (negation / linker: far too common in Tagalog, would falsely negate "tigil na"),
Arabizi `mo` (Tagalog "mo" = "your"), Malayalam half-quantity words (unsure). Rule from the brief: if unsure, leave it out.
Ambiguous short words (`do`, `la`, `ma`, `a`, `an`) carry `ambiguous: true` and only count when a same-language
neighbour (or `lang_hint`) supports them.

## D7 — Bare numbers are never enough
A bare digit with no unit word ("2 5") is not attributed to any fact. Numeric facts with only bare numbers in the
reply become `unclear`, not `understood`.

## D8 — Embedding fallback ships disabled until calibrated
`fallback.py` is implemented (lazy `multilingual-e5-small`) but its thresholds in `fallback_config.json` are `null`
until calibrated on the eval set; with null thresholds it returns nothing. It can only touch `condition` facts that
have no lexicon hit, never numerics.

## D9 — Eval honesty
The synthetic eval variants are generated from templates written by the team using vocabulary the lexicon already
knows, so they overestimate real-world accuracy. They are flagged `synthetic=true` and reported separately from
hand-written replies. We do not report baseline numbers unless the baseline actually ran.

## D10 — Evaluation history (kept here because it is history, not a result)
* Development set: 72 hand-written replies (`hw-*`) + 447 synthetic. While building it we read every engine error and fixed the
  *general* bugs they exposed (Arabizi digit-words being split, "do bottle", "roz do baar", "a day" read as a duration,
  dates blaming each other, one typo'd negator producing the only false "understood"). So those numbers are development numbers.
* Blind held-out set: 39 harder replies (`ho-*`) written after the engine was frozen for that round and evaluated **once**.
  **First blind run: 87.4% accuracy, 0 false "understood" out of 41 not-understood facts** (all errors on the safe side:
  missing/unclear, plus one question-style reply flagged "wrong").
* We then fixed what that run exposed (numbers never fuzzy-match short words: Hindi "aankh" had matched Malayalam 5;
  "thrice daily for a week"; plural "marrat"; Hindi "boond"). The held-out set is therefore **no longer blind**; its later numbers
  are development numbers too. Real blind data must come from teammates (README: "Adding real replies").
* The false-"understood" rate is 0 on our data, but the denominators are small (69 hand-written, 41 held-out) and the data
  are ours. 0/41 is NOT evidence of 0%. The known residual risk is a misspelled negation word we do not recognise.

## D11 — Safety rules added after reading the errors
* Number words never fuzzy-match (only exact / by-ear key / suffix), because a spurious digit is worse than a missed one.
* Negation words tolerate one dropped letter ("hndi" -> "hindi").
* A lone "a/1 day" after a frequency word ("twce a day", "sa isang araw") is a rate, not a 1-day duration. "for a day" still is one.
* "daily/roz" alone is weak evidence (inferred), never a hard "wrong".
* Weak (inferred) values can support a result but never contradict one.
* Two unmatched facts of the same kind + one stray value => `unclear`, not `wrong` (we can't know which fact it answers).
