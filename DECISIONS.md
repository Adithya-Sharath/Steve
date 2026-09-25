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

## D12 — Negation robustness (supersedes part of D6)
*Trigger:* `dnt stop if rash` returned `understood`, the worst possible error.
* Added SMS/typo negators: `dnt, donot, "do nt", didnt, "did not", dontt, wont` (English); `mt`, `na` (Hindi); `mo` (Arabizi); `di`, `hnd/hndi` (Tagalog); `nt`, `dun`, `dn` (English SMS). `dont, nhi, nai, wag, la` already existed.
* **D6 said `na` and `mo` were deliberately excluded** (Tagalog "na" = already/linker, would negate "tigil na"; Tagalog "mo" = "your"). They are now included **but guarded**, so those Tagalog uses stay safe (tested):
  * `na` (Hindi) only counts within 2 tokens of a Hindi verb ("band na karo"); otherwise it stays a Tagalog filler.
  * `mo` (Arabizi) and `di` (Tagalog) are `ambiguous`: they count only with same-language neighbours.
  * `nt`/`dun`/`dn` count only right next to an English verb (stop, take, call...): Tagalog "dun" = "there".
* The matcher now fuzzy-matches **known negators only** (`_negator_typos`): SMS vowel-dropping (`dnt`->`dont`), one dropped/inserted letter (len>=4), one substitution (len>=5), first and last sound must match; ambiguous negators never fuzzy-match. Ordinary look-alikes (`note`, `dot`, `don`, `nod`) are tested not to match.
* Everything here can only move a result towards `negated`/`unclear`, never towards `understood`.
* Also: `eval/update_readme.py` now refreshes the test counts in the README (and refuses to if a suite is red).

## D13 — Concessive clauses can never be `understood`
*Trigger:* `stop only after 5 days even if rash` returned `understood`.
* New lexicon category `concessive`: English `even if / even with / even when / even though / despite / still / anyway / regardless / although / though / no matter`, Hindi `bhi`, Tagalog `kahit (na)`; Malayalam `-alum` (`vannalum`) is detected on the token itself (>= 6 letters, unmatched suffix).
* Rule (`compare.concessive_near`): a concessive within **3 content tokens of the condition's trigger, in the same sentence**, means the reply undermines the rule:
  * an un-negated `continue` action nearby => **`negated`** ("even if rash, continue");
  * otherwise => **`unclear`** ("stop only after 5 days even if rash" stays `unclear`, not `negated`, because we cannot read "only after 5 days" as "don't stop").
  * an already-negated action (`nirthanda`, `don't stop`) stays `negated`.
* **Exemption:** a fact whose own action is `continue` ("keep taking it even if rash") ignores concessives, because "even if" is the natural wording of that rule.
* Far-away or other-sentence concessives are ignored ("main bhi do goli lunga, rash aaye to band karo" is still understood), since Hindi `bhi` = "also" is everywhere.
* Known limit: `avoid` facts are unchanged (an un-negated "travel" is already `unclear`).

## D14 — Copy-paste detection
*Trigger:* a reader who pastes the sender's message back proves nothing, but every fact matched perfectly.
* `check_reply(..., message=...)` (new optional argument; the API passes the stored message, `/check` and `/analyze` accept an optional `message`). If the reply is a paste, **every fact becomes `unclear`** with the exact reason *"Reply looks copied from the message; ask them to say it in their own words."*, `flags=["copied"]`, no evidence, no numeric decision at all.
* Similarity = `rapidfuzz.fuzz.token_set_ratio` on normalised words, threshold **> 0.85** (as requested). **Deviation, on purpose:** `token_set_ratio` is 100 whenever the reply's words are a *subset* of the message's, so the correct short answer "2 tablets after food twice a day 5 days" would be flagged. We therefore also require the reply to have **>= 4 words and >= 60% as many words as the message** (`copycheck.py`). Tested: short and paraphrased answers are never flagged.
* **Second deviation, found by the eval:** with `token_set_ratio` (+ length guard) alone, 10 of our own honest English restatements ("1 drop 3 times a day for 10 days") were flagged as copies, because they reuse the message's words (`token_set_ratio` ~ 100) and the eval accuracy on hand-written data fell from 98.7% to 90.4%. A reply is now a copy only if it **also** matches the message in *order*: `fuzz.ratio` on the normalised strings > 0.85. Measured on our data, real pastes score 97-100 on that measure and honest restatements <= 82. Cost: a paste with several words removed or reordered is no longer caught; it is then judged normally.
* Near-verbatim pastes with a changed number ("3 tablets ...") are still flagged `unclear` rather than `wrong`: we lose that detail on purpose because the reader still didn't say it in their own words.
* Aggregation: a copied reply may fill an empty slot with `unclear` but **never erases an earlier real result**; a later real answer overrides it.
* UI: the results page shows a banner ("This reply looks copied from your message ...", with the follow-up button) and each card carries a "copied from the message" tag. The landing playground and inspector pass the message, so pasting it there demonstrates the rule.
* Storage: `FactResultRow.flags` (JSON). Existing SQLite files are migrated in place at start-up (`db._ensure_columns`, tested).
* Eval: 3 hand-written copy rows (gold: all `unclear`) added; `run_engine.py` now passes the message.

## D15 — English shorthand and squashed number+unit tokens
*Trigger:* SMS-style replies ("2tab aftr fud 2wice a day 5dys stp if rash") were mostly unreadable.
* Squashed digit+letters tokens already split when the letters are a unit/counter word (`5days`, `2tabs`, `3x`, `15min`); the lexicon now knows the SMS spellings, so `5dys`, `5dy`, `2tab`, `2tabl`, `1wk`, `2wks`, `3wek` split and read correctly. Words that *contain* a digit as a letter are matched whole, never split: `2wice` (twice), `3rice`, `1ce`, `b4` (before), and Arabizi `3ashra`, `7ma`.
* Added English spellings (all ordinary exact variants, no new fuzzy matching): after `aftr aftar aftah`, before `b4 bfr befor`, food `fud`, stop `stp`, tablet `tabl tblt tabz`, day `dys dy dayz`, week `wek weks`, twice `2wice twise twyce`, thrice `3rice`, once `1ce`, times `tmes`, daily `dly`, morning `mrng morn`, night `nite nyt`. `tabs`, `wk`, `wks` already existed.
* Guards: `dy`/`wk`/`dys` with no number never make a duration; `b4` never becomes the number 4 (tested). The lexicon's sound-key collision test still passes, so no shorthand is equally close to two different meanings.
* Combined with D12, `dnt stp if rash` is never `understood`.

## D16 — Sender authentication (privacy)
*Trigger:* the reader page said "Only <sender> sees your answer", but anyone who guessed a message id could call the sender endpoints, and on a public deployment anyone could spend the LLM quota via `/settings/llm`.
* **Chosen fix (preferred over softening the copy):** a per-browser **sender key**. The browser generates `sk_<32 random chars>` once (localStorage; memory-only if storage is blocked) and sends it as `X-Sender-Key`. The server keeps only its **SHA-256 hash** on each message (`Message.owner_hash`) and compares in constant time. A capability, not a password: no accounts, no login, nothing to reset.
* Require the key (else **403**): `POST /messages`, `GET /messages`, `GET /messages/{id}`, `POST /messages/{id}/confirm`, `POST /messages/{id}/followup`, `GET /messages/{id}/stream`, `POST /demo/seed`, `POST /settings/llm`. Someone else's message (or a legacy row with no owner) is also 403; an unknown id is 404. `GET /messages` returns only the caller's messages.
* **Unchanged / open by design:** reader endpoints (`GET /r/{token}`, `POST /r/{token}/reply`: the token is the capability), `/health`, `/check`, `/analyze`, `/eval/results`, `/demo/scenarios` (no user data).
* **EventSource cannot set headers**, so the stream alone also accepts `?key=`. Caveat: a key in a URL can appear in server/proxy logs; use HTTPS and treat logs as sensitive. All other endpoints take the header only.
* **Demo still works:** `/demo/seed` now creates the four scenarios *for the calling sender* (ids `demo-<scenario>-<first 6 hex of the key hash>`), so two visitors never see or reset each other's demo data. The `/demo` page and the "Load demo data" button work unchanged.
* **`/settings/llm`** stays a global switch but now needs *a* valid key, so an unauthenticated visitor cannot flip it. It still lets any sender toggle the LLM for everyone; a real deployment should set `LLM_ENABLED` in the environment and leave the toggle to demos (README).
* **Limitations:** the key lives in one browser: clearing site data or switching device loses access to that browser's messages (they stay in the database). No key rotation or sharing yet. Existing rows created before this change have no owner and are not readable. `create_all` cannot alter tables, so `db._ensure_columns` adds `message.owner_hash` in place (tested).
