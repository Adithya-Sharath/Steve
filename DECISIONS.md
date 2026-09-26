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

## D17 — API container binds to `$PORT`
*Trigger:* `api/Dockerfile` hard-coded `--port 8000`, which fails on hosts that inject `PORT` (Render, Railway, Cloud Run).
* `CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]`. The JSON-array form cannot expand variables, hence the shell; `exec` keeps uvicorn as PID 1 so it receives SIGTERM. Default stays 8000, so `docker compose` and local runs are unchanged (the compose healthcheck still targets 8000).
* Tests: assert the CMD shape (no hard-coded port), execute the shell string with `uvicorn` swapped for `echo` under `PORT` unset and `PORT=10000`, and forbid inline comments after instructions (a trailing `# ...` on `EXPOSE` would be parsed as ports).
* **Not verified by building the image**: Docker Desktop was not running on this machine. The README deploy notes still apply.

## D18 — Screenshots come from a production build
*Trigger:* the first README screenshots were taken against `next dev`, so the Next.js dev badge ("N") was visible in the corner.
* All images in `docs/screenshots/` were retaken against `next build && next start` with the API running, using a Playwright script that sets a sender key in the browser and seeds the demo through the authenticated API (D16). The script also asserts that no Next dev indicator element exists in the DOM (`dev indicator in DOM: false`) and that there were no console errors.
* Added `copied.png` (the copy-paste banner, D14) and put it in the README table.
* Images are regenerated by hand; they are not a test. If the UI changes, retake them the same way (production build, never dev).

## D19 — Bug found by the final checks: README test counts were never refreshed
*Found while running the full check suite:* D12 said `eval/update_readme.py` refreshes the test counts in the README, but `main()` never called `refresh_counts()` (a later `ruff --fix` had rewritten a line my patch depended on, and the patch failed silently). The README kept saying "145 engine + 15 API tests" while the real counts were 275 and 38.
* Fixed the wiring; the counts now come from real `pytest` runs (`engine`, `api`), and the script refuses to write numbers if a suite is red.
* Added two tests (`api/tests/test_readme_counts.py`): one for the regex rewrite of every place the README mentions counts, one asserting `main()` actually calls `refresh_counts` (the exact regression).
* Lesson recorded: after editing a script with an automated patch, assert the patch applied (I now assert on every replacement in patch scripts).
* **Addendum (found by the final checks):** making the eval scripts write LF endings introduced a worse bug for a moment: `update_readme.py` opened `README.md` for writing *before* computing the new text, so when the "tests are not green" guard aborted, the README was truncated to empty (caught in the working tree before it was committed; restored from git). Fixed by computing everything first, then writing. Tests now cover the behaviour instead of the source text: a red suite and missing markers leave the README byte-for-byte unchanged, and a green run rewrites table + counts with LF endings. `common.dump`, `write_replies` and the README writer all emit LF, so re-running `make eval` on Windows changes only the `generated_at` timestamp (verified).

## D20 — Root `CLAUDE.md` and `PROGRESS.md`
*Request:* create them "as specified in `docs/build-prompt.md`". **The brief does not specify either file** (searched for `CLAUDE.md` / `PROGRESS`; no match), so the contents follow common practice rather than a spec:
* `CLAUDE.md` = rules that must not be broken (the brief's principles + the safety rule from D11), commands with Windows equivalents, layout, the change procedure (test -> eval -> README refresh -> DECISIONS -> one commit per fix), auth/web/environment gotchas learned the hard way (D19).
* `PROGRESS.md` = phase table, the numbers from the final verification run (nothing typed from memory), decisions index, an honest known-gaps list, the human checklist, and next steps.
* If you had a specific template in mind, send it and I will reshape both files to match.

## D21 — Buttons with depth (21st.dev "Press Depth", adapted)
*Request:* make buttons feel high-quality: depth and animation on hover and click. No data-flow, API, auth or prop changes.
* **Source:** 21st.dev MCP (free tier: **2 component-code downloads per day**; #1 used here). Component: *Press Depth* by ddoemonn (`/r/ddoemonn/press-depth`), chosen from previews over Magic Button / Pop Button / 3D Button because it has the raised lip **and** a spring press that tilts toward the pointer.
* **What we kept:** the pointer-origin maths (press tilts toward where you touch), "press cancels when the pointer slides off", Space/Enter support. **What we changed:** it now writes `data-pressed` + `--tilt-x/--tilt-y` CSS variables instead of React state + motion springs (no re-renders, `hooks/use-press-depth.ts`), and the look is our tokens (`.btn-raised`, `.btn-primary/-outline/-secondary/-danger` in `globals.css`): hard lip + soft glow + inner highlight, hover lifts 1px with a sheen sweep, press sinks the surface onto the lip with an overshoot spring curve. Ghost/link stay flat but squash slightly on press. Chips/tabs/preset cards got a lighter `.pressable` version.
* **Works for links too:** `buttonVariants` moved to `components/ui/button-variants.ts` (no `"use client"`), so Server Components and `<Link>` CTAs get the same look; `button.tsx` is now a client component that re-exports it. Only `app/page.tsx` (a Server Component) needed its import changed. Props of `Button` are unchanged.
* **Accessibility / motion:** focus ring kept; disabled buttons never press or lift; `prefers-reduced-motion` turns transitions and the tilt off (the press still registers); dark mode derives the lip/glow from `--primary`, `--card`, `--border`.
* **Bug caught while verifying:** the hover rule out-ranked the press rule (equal-looking selectors, higher specificity), so pressing did nothing while hovering. Fixed by giving the press rule the same specificity and later position; verified in a real browser (matrix3d press, lip collapses).
* **Dependencies:** none added (no new npm package; `framer-motion` untouched).
* **Verified:** `tsc`, `eslint`, production build clean; browser flow test 16/16; a dedicated button test (tilt vars from pointer origin, slide-off cancels, Space key press/release, disabled inert, reduced motion) 13/13; Lighthouse accessibility 100 on `/`, `/how-it-works`, `/app`, `/demo`, `/app/new`.
* **Found on the way (not fixed, out of scope):** the browser flow test flips the *global* LLM switch. With a real Gemini key configured, "Find key facts" then calls Gemini and waits on it (there is no timeout/fallback budget in `llm_extract`), which stalled a screenshot. Worth adding a short timeout that falls back to the built-in extractor.

## D22 — Landing: stats bento with tickers, and a timeline for "how it works"
*Request:* one standout component for the "problem" stats and a better "how it works" section; keep the hero demo animation.
* **21st download #2 of 2 for today** (free tier: 2/day; next reset tomorrow): *Number Ticker* by danielpetho (`/r/danielpetho/basic-number-ticker`), chosen for its analytics-cards demo (bento with a tinted fill rising in each card). **Adapted, not pasted:** the ticker now renders a motion value directly (no React re-render per frame) and adds decimals, prefix/suffix, in-view trigger, stagger `delay` and reduced-motion; the bento layout uses our tokens: fills are the status colours (`--wrong-soft` for the 19% wrong, `--understood-soft` for the 11.9%, `--unclear-soft`, `--teal-soft`), so dark mode is automatic. The 4th card is a full-width strip so the grid tiles without a hole. Sources/links and the exact numbers are unchanged.
* **Timeline: built by us**, structure inspired by the 21st "Vertical How It Works Timeline" preview (numbered nodes on a rail; not downloaded, so no code was taken). Numbered nodes light up as they scroll into view, the rail fills with scroll progress (`useScroll` + `useSpring`), and each step now carries a real example (the pharmacy message, its fact chips, the Manglish reply, the status badges).
* `NumberTicker` is shared with the `/eval` page (`MetricTile`), so those tiles benefit too; its API is unchanged.
* **Bug found and fixed:** the landing page threw React hydration error #418 with `prefers-reduced-motion` on, because components *branched their render* on framer's `useReducedMotion()`, which reads the media query synchronously on the client (different HTML from the server). Present since the hero demo was written; found only because this round scanned every page in every mode. New hydration-safe `hooks/use-reduced-motion.ts` (`useSyncExternalStore` with a `false` server snapshot) is used by the hero demo, pipeline diagram and ticker; the timeline rail's reduced-motion override is pure CSS. **Scan: 8 pages x light/dark x normal/reduced = 32 loads, zero console or hydration errors.**
* **No new dependencies.** Verified: `tsc`, `eslint`, production build; browser flow test 16/16; Lighthouse accessibility 100 on `/`, `/how-it-works`, `/eval`, `/app`, `/demo`; counters reach their exact final values in light, dark, phone width and reduced motion.

## D23 — Results page: staggered pending -> status resolve
*Request (target 2):* a more satisfying fact-card resolve, "if 21st has a good fit".
* **No 21st component used** (0 of the 2 free daily downloads were left, and nothing in the search results fit better than what `framer-motion` already gives us). Built in `components/fact-card.tsx`; the only API change is an **optional** `order` prop (default 0), so every other user of `FactCard` (playground, inspector) is unchanged.
* **The sequence** when a reply arrives over SSE: the shimmer chip fades and shrinks out (`AnimatePresence mode="wait"`), cards resolve **one after another** (0.09 s stagger by list position), each with a one-off sweep in its status colour across the card, the status badge springs in, the icon tile and border cross-fade to the status colour (500 ms), and the reason text slides in last. The sweep replays if a card's status changes.
* **Accessibility / motion:** `prefers-reduced-motion` hides the sweep (`motion-reduce:hidden`, verified `display: none`) and `MotionConfig` disables the transforms; the badge keeps its text + icon (never colour alone). **axe-core (WCAG 2.1 AA): 0 violations** on the results page in the pending, resolved and copied-banner states, dashboard and reader, light and dark (Lighthouse cannot sign in as a sender, so axe ran in a signed-in browser).
* **Bug found while capturing frames and fixed:** the transcript's highlight sweep briefly showed the browser's default **yellow `<mark>` background** while the gradient grew from 0%. The base background is now transparent (verified in production: computed `rgba(0, 0, 0, 0)`).
* **Verified:** `tsc`, `eslint`, production build; browser flow test 16/16 (the test now restores the global LLM switch it flips); frame capture at 0/250/550/900/2000 ms shows 5 pending -> 0 with the right statuses (wrong, missing, understood x3) in normal, reduced-motion and dark; hydration/console scan 32 loads clean.
* **Not shipped:** a frame-strip image of the animation: frames from separate screenshots scroll differently and looked misleading. Record a short screen capture for the demo video instead.

## D24 — Reader: record button with depth, mic-reactive halo and a 30-second ring
*Request (target 3):* a clearly better record button/waveform, only if it stays mobile-first and accessible.
* **No 21st component** (no downloads left today; nothing in scope beat improving what we have). Changes are confined to `components/voice-recorder.tsx` plus `.btn-record` / `.record-breathe` in `globals.css`; the recorder's props, the WAV conversion and the upload path are untouched.
* **What changed:** (1) the big button is our shared `Button` (D21), so it has the raised lip, the press that sinks and tilts toward the finger, and focus ring; recording turns it red (`--wrong`) with its own lip. (2) An idle button "breathes" a soft ring to invite the first tap. (3) The halo behind it follows the **real microphone level** (`AnalyserNode` RMS -> `--level`, smoothed), replacing a purely time-based pulse. (4) A ring around it fills over the 30 s limit (turns amber for the last 5 s); it is decorative, the timer text remains the accessible readout. Waveform bars are unchanged.
* **Reduced motion:** no breathing, the halo is not driven by the mic (`--level` stays unset), the progress ring still shows (it is information, not decoration of motion), and recording works end to end.
* **Verified with Chromium's fake microphone** (voice UI forced on by patching only the `GET /r/{token}` response; Send never clicked, so nothing reached Sarvam): tap starts recording and the label flips to "Stop recording"; halo level varies with the input (0.00-0.22); ring fills; timer counts; stop -> audio playback + "Record again" + "Send"; record button inert after recording; "Record again" resets; 128 px touch target; **axe WCAG 2.1 AA: 0 violations while recording**; no page errors. 16/16 recorder checks, plus the browser flow test 16/16, the 32-load hydration scan, the 13-check button behaviour test and the axe sweep all still pass.
* **Not verified:** a real phone and real speech (needs HTTPS and a Sarvam key with `STT_ENABLED=true`).
* **Crash note:** the laptop crashed mid-session; nothing committed was lost. One baseline cache file was truncated by the crash and made the runner fail on restart. `eval/run_baseline.py` now discards an unreadable cache entry and writes cache files atomically (temp file + `os.replace`).
