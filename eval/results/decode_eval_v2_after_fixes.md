# Decode Phase 3 evaluation (D44), set v2, run: after_fixes

Frozen evaluation set `data/decode/eval_v2.csv` (sha256 3732415f656e92eb), built from `workplace_instructions_v2.csv` (sha256 5014b4f52f9d097c): 245 scored rows from 72 hand-written UAE workplace instructions. **Synthetic, one author: sentences, gold labels and by-ear respellings.** **Status: CONTAMINATED.** Its first scoring run (eval/results/decode_eval_v2_first_run.md) showed a clock-time bug, an over-eager object rule and a vocabulary gap, which were fixed afterwards (D44); these numbers are a re-score after those fixes, not a fresh test. It measures whether the decoder does what its author intended on a sample it was not built from; it says nothing about how real workers write or speak (real-world validation is missing, D42). Every rule, phrase and word list is `verified: false`.

## 1. False-alarm rate (headline)

A correctly written sentence for which the card shows any change or any clarifying question.

| Rows | Sentences | False alarm (any) | False rewrite (silent edit) | Question only |
|---|---:|---|---|---|
| All correct sentences | 144 | 1.4% (2/144; 95% 0-5%) | 0.0% (0/144; 95% 0-3%) | 1.4% (2/144; 95% 0-5%) |
| Typed correctly | 72 | 0.0% (0/72; 95% 0-5%) | 0.0% (0/72; 95% 0-5%) | 0.0% (0/72; 95% 0-5%) |
| Voice transcript, correct | 72 | 2.8% (2/72; 95% 1-10%) | 0.0% (0/72; 95% 0-5%) | 2.8% (2/72; 95% 1-10%) |

By the accent hint given with the sentence (typed and voice together):

| Hint | Sentences | Any false alarm | False rewrites |
|---|---:|---:|---:|
| ar | 29 | 0 | 0 |
| hi | 29 | 0 | 0 |
| ml | 29 | 0 | 0 |
| none | 28 | 1 | 0 |
| tl | 29 | 1 | 0 |

## 2. Typed-text decode accuracy (headline)

Sentences typed by ear (respelled). *Exact* = the card's changes give the intended sentence; *asked* = a clarifying question offers the meant word (no silent guess); *left as typed* = nothing decoded and nothing asked (a miss; the misspelling stays visible in the text); *wrong rewrite* = the card changed something and the result is not the intended sentence (wrong-but-confident). (Left-as-typed was split from wrong rewrite after the first scoring run, because the first version lumped them.) **In-pack** = the respelling is one the accent packs are meant to cover; **out-of-pack** = a pattern they do not model (th->f, ee->i, h-dropping, ...), so this row is the honest limit.

| Respellings | Sentences | Exact | Asked | Exact or asked | Left as typed | Wrong rewrite (wrong-but-confident) |
|---|---:|---|---|---|---|---|
| In-pack | 67 | 94.0% (63/67; 95% 86-98%) | 4.5% (3/67; 95% 2-12%) | 98.5% (66/67; 95% 92-100%) | 0.0% (0/67; 95% 0-5%) | 1.5% (1/67; 95% 0-8%) |
| Out-of-pack | 34 | 0.0% (0/34; 95% 0-10%) | 0.0% (0/34; 95% 0-10%) | 0.0% (0/34; 95% 0-10%) | 100.0% (34/34; 95% 90-100%) | 0.0% (0/34; 95% 0-10%) |
| All | 101 | 62.4% (63/101; 95% 53-71%) | 3.0% (3/101; 95% 1-8%) | 65.3% (66/101; 95% 56-74%) | 33.7% (34/101; 95% 25-43%) | 1.0% (1/101; 95% 0-5%) |

By accent hint (in-pack and out-of-pack together):

| Hint | Sentences | Exact | Asked |
|---|---:|---:|---:|
| ar | 20 | 13 | 0 |
| hi | 17 | 10 | 1 |
| ml | 21 | 14 | 0 |
| none | 24 | 16 | 2 |
| tl | 19 | 10 | 0 |

## 3. Where / when / what / how-much extraction accuracy (headline)

For every slot that has a gold value: *correct*, *partial* (right but incomplete: "gate" for "main gate", "bring" for "bring trolley"), *empty* (nothing extracted: the safe failure) or *wrong* (a value that is not part of the gold: the dangerous one). (Partial was split from wrong after the first scoring run, because the first version counted every incomplete value as wrong.) *Spurious* = the slot had no gold value but the card filled it anyway (of all rows whose gold is empty).

| Rows | Slot | Gold present | Correct | Partial | Empty | Wrong | Spurious fills |
|---|---|---:|---|---:|---:|---|---|
| Typed correctly | where | 36 | 91.7% (33/36; 95% 78-97%) | 1 | 2 | 0.0% (0/36; 95% 0-10%) | 2.8% (1/36; 95% 0-14%) |
| Typed correctly | when | 31 | 90.3% (28/31; 95% 75-97%) | 0 | 3 | 0.0% (0/31; 95% 0-11%) | 0.0% (0/41; 95% 0-9%) |
| Typed correctly | what | 60 | 100.0% (60/60; 95% 94-100%) | 0 | 0 | 0.0% (0/60; 95% 0-6%) | 0.0% (0/12; 95% 0-24%) |
| Typed correctly | how_much | 10 | 100.0% (10/10; 95% 72-100%) | 0 | 0 | 0.0% (0/10; 95% 0-28%) | 0.0% (0/62; 95% 0-6%) |
| Voice transcript, correct | where | 36 | 86.1% (31/36; 95% 71-94%) | 1 | 4 | 0.0% (0/36; 95% 0-10%) | 2.8% (1/36; 95% 0-14%) |
| Voice transcript, correct | when | 31 | 90.3% (28/31; 95% 75-97%) | 0 | 3 | 0.0% (0/31; 95% 0-11%) | 0.0% (0/41; 95% 0-9%) |
| Voice transcript, correct | what | 60 | 100.0% (60/60; 95% 94-100%) | 0 | 0 | 0.0% (0/60; 95% 0-6%) | 0.0% (0/12; 95% 0-24%) |
| Voice transcript, correct | how_much | 10 | 100.0% (10/10; 95% 72-100%) | 0 | 0 | 0.0% (0/10; 95% 0-28%) | 0.0% (0/62; 95% 0-6%) |
| Typed by ear, in-pack | where | 34 | 94.1% (32/34; 95% 81-98%) | 0 | 2 | 0.0% (0/34; 95% 0-10%) | 3.0% (1/33; 95% 1-15%) |
| Typed by ear, in-pack | when | 29 | 89.7% (26/29; 95% 74-96%) | 0 | 3 | 0.0% (0/29; 95% 0-12%) | 0.0% (0/38; 95% 0-9%) |
| Typed by ear, in-pack | what | 56 | 96.4% (54/56; 95% 88-99%) | 0 | 2 | 0.0% (0/56; 95% 0-6%) | 0.0% (0/11; 95% 0-26%) |
| Typed by ear, in-pack | how_much | 9 | 88.9% (8/9; 95% 56-98%) | 0 | 1 | 0.0% (0/9; 95% 0-30%) | 0.0% (0/58; 95% 0-6%) |
| Typed by ear, out-of-pack | where | 18 | 27.8% (5/18; 95% 12-51%) | 0 | 11 | 11.1% (2/18; 95% 3-33%) | 0.0% (0/16; 95% 0-19%) |
| Typed by ear, out-of-pack | when | 12 | 58.3% (7/12; 95% 32-81%) | 3 | 2 | 0.0% (0/12; 95% 0-24%) | 0.0% (0/22; 95% 0-15%) |
| Typed by ear, out-of-pack | what | 28 | 60.7% (17/28; 95% 42-76%) | 0 | 9 | 7.1% (2/28; 95% 2-23%) | 0.0% (0/6; 95% 0-39%) |
| Typed by ear, out-of-pack | how_much | 4 | 0.0% (0/4; 95% 0-49%) | 0 | 3 | 25.0% (1/4; 95% 5-70%) | 0.0% (0/30; 95% 0-11%) |

Negation kept: 41 of 41 negated sentences still contain the negation in the plain English, or the card asked about a possible hidden negation (a negation must never be silently lost).

## 4. Voice safety net catch rate (secondary; read the labels)

* **Synthetic, author-written, tuned on it:** 125 of 188 risky words caught (66.5%: 36 rewritten, 89 asked), 4 wrong rewrites; false alarm 0 of 265 clean sentences. This set was used to set the margins, so it is an upper bound.
* **Held-out L2-ARCTIC (test only, Sarvam transcripts, D43): catch 0 of 72 risky words** (0 of 105 on the whatsapp-snr10 run). The errors in that data (coal -> cold, boat -> board) fall outside the where / when / what / amount / negation slots the net watches, so the net correctly does not look at them: the number says the net is not a general speech-to-text error fixer, and nothing about how it would do on workplace instructions.
* Whether real voice notes break critical-slot words at all is untested. The only real-audio evidence is D42: on clean and whatsapp-snr10 audio, numbers, times, places and negations came back right 48/57 and 47/57 times with 0 wrong real words (the rest not aligned or kept).

## 5. Every miss, listed

45 rows with a false alarm, a wrong-but-confident decode, or a wrong / spurious slot value (empty slots are counted above, not listed):

* `ew0009` [typed_clean, tl] `go to block c` -> where partial: got 'block', gold 'block c'
* `ew0066` [typed_clean, ar] `the lift is on the second floor` -> where spurious: got 'second floor', gold ''
* `ew0074` [voice_clean, tl] `Wait at the fire exit.` -> FALSE ALARM:  | asked: Four or five or fire?
* `ew0081` [voice_clean, ar] `Go to block c.` -> where partial: got 'block', gold 'block c'
* `ew0085` [voice_clean, none] `Come to the back gate.` -> FALSE ALARM:  | asked: Bank or back?
* `ew0138` [voice_clean, ml] `The lift is on the second floor.` -> where spurious: got 'second floor', gold ''
* `ew0173` [typed_ear in-pack, none] `bay one hundred and twenty dirhams` -> asked: Pay or bay?
* `ew0182` [typed_ear in-pack, hi] `newer open de door` -> asked: Never or newer?
* `ew0194` [typed_ear in-pack, none] `pay dirty dirhams at de counter` -> asked: Thirty or dirty?
* `ew0205` [typed_ear in-pack, none] `te lift is on te second floor` -> where spurious: got 'second floor', gold ''
* `ew0211` [typed_ear in-pack, none] `tank you for te help` -> WRONG REWRITE: decoded as 'tank you for the help' (changes: te->the)
* `ew0212` [typed_ear out-of-pack, ml] `go to the istaff rum` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0213` [typed_ear out-of-pack, tl] `mit me at the swimming pul` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0214` [typed_ear out-of-pack, tl] `park behind the generator rum` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0215` [typed_ear out-of-pack, hi] `come to the schul gate` -> LEFT AS TYPED (nothing decoded, nothing asked) ; where wrong: got 'schul gate', gold 'school gate'
* `ew0216` [typed_ear out-of-pack, ar] `brin the tuls to level two` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0217` [typed_ear out-of-pack, none] `come to rum eleven` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0218` [typed_ear out-of-pack, ml] `wait near the ospital entrance` -> LEFT AS TYPED (nothing decoded, nothing asked) ; where wrong: got 'ospital entrance', gold 'hospital entrance'
* `ew0219` [typed_ear out-of-pack, ml] `mit at the gym` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0220` [typed_ear out-of-pack, none] `park in the visitor parkin` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0221` [typed_ear out-of-pack, ar] `send the driver to the otel` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0222` [typed_ear out-of-pack, hi] `come tomorrow mornin` -> LEFT AS TYPED (nothing decoded, nothing asked) ; when partial: got 'tomorrow', gold 'tomorrow morning'
* `ew0223` [typed_ear out-of-pack, hi] `come after icha` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0224` [typed_ear out-of-pack, hi] `finich by friday` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0225` [typed_ear out-of-pack, ar] `istart at six firty` -> LEFT AS TYPED (nothing decoded, nothing asked) ; when partial: got '6', gold '6 30'
* `ew0226` [typed_ear out-of-pack, tl] `come at thri pm` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0227` [typed_ear out-of-pack, tl] `come at nun tomorrow` -> LEFT AS TYPED (nothing decoded, nothing asked) ; when partial: got 'tomorrow', gold 'noon tomorrow'
* `ew0228` [typed_ear out-of-pack, none] `pay one undred and twenty dirhams` -> LEFT AS TYPED (nothing decoded, nothing asked) ; how_much wrong: got '20 dirhams', gold '120 dirhams'
* `ew0229` [typed_ear out-of-pack, tl] `the salary is two fousand dirhams` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0230` [typed_ear out-of-pack, ml] `give me fiftin dirhams` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0231` [typed_ear out-of-pack, ar] `never open the dur` -> LEFT AS TYPED (nothing decoded, nothing asked) ; what wrong: got 'never open dur', gold 'never open door'
* `ew0232` [typed_ear out-of-pack, none] `do not brin the truck to the yard` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0233` [typed_ear out-of-pack, ml] `don't take the keys ome` -> LEFT AS TYPED (nothing decoded, nothing asked) ; what wrong: got 'don't take keys ome', gold 'don't take keys'
* `ew0234` [typed_ear out-of-pack, tl] `come to the parkin at six` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0235` [typed_ear out-of-pack, ar] `mit me at the reception tomorrow at eight` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0236` [typed_ear out-of-pack, ml] `brin the files to flur five today` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0237` [typed_ear out-of-pack, tl] `pay firty dirhams at the counter` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0238` [typed_ear out-of-pack, hi] `take the parcel to buildin two tomorrow` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0239` [typed_ear out-of-pack, ar] `abibi brin the box to the lobby` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0240` [typed_ear out-of-pack, ml] `mafi muchkila come at five` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0241` [typed_ear out-of-pack, none] `inchallah the truck comes tomorrow` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0242` [typed_ear out-of-pack, ar] `the lift is on the second flur` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0243` [typed_ear out-of-pack, hi] `gud evenin sir` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0244` [typed_ear out-of-pack, tl] `my friend is in the ospital` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ew0245` [typed_ear out-of-pack, tl] `fank you for the elp` -> LEFT AS TYPED (nothing decoded, nothing asked)

Empty slots (nothing extracted although gold had a value): {'where': 19, 'when': 11, 'what': 11, 'how_much': 4}.

## 6. What this evaluation cannot show

* No real voice notes, no real typed messages (D42). All text is author-written; the by-ear respellings are generated by letter rules, real people vary far more.
* One author wrote the sentences and the gold, so the results reflect the author's own idea of the task. A different author would find different gaps.
* The in-pack rows use the same kinds of sound swaps the packs were built from, so the in-pack accuracy is optimistic; the out-of-pack rows show what happens outside them.
* No baseline comparison yet (a Gemini baseline on the same set is planned but not run: it costs API calls).

