# Decode Phase 3 evaluation (D44), set v1, run: after_fixes

Frozen evaluation set `data/decode/eval_v1.csv` (sha256 b92dbd62c860dffb), built from `workplace_instructions.csv` (sha256 5a747434d5093c57): 458 scored rows from 136 hand-written UAE workplace instructions. **Synthetic, one author: sentences, gold labels and by-ear respellings.** **Status: CONTAMINATED.** The first scoring run of this set (eval/results/decode_eval_v1_first_run.md) was used to find and fix gaps in the extractor and the typed decoder (D44), so these numbers are tuned-on numbers, not a fresh test. Use the first-run file and the v2 set for honest numbers. It measures whether the decoder does what its author intended on a sample it was not built from; it says nothing about how real workers write or speak (real-world validation is missing, D42). Every rule, phrase and word list is `verified: false`.

## 1. False-alarm rate (headline)

A correctly written sentence for which the card shows any change or any clarifying question.

| Rows | Sentences | False alarm (any) | False rewrite (silent edit) | Question only |
|---|---:|---|---|---|
| All correct sentences | 272 | 0.0% (0/272; 95% 0-1%) | 0.0% (0/272; 95% 0-1%) | 0.0% (0/272; 95% 0-1%) |
| Typed correctly | 136 | 0.0% (0/136; 95% 0-3%) | 0.0% (0/136; 95% 0-3%) | 0.0% (0/136; 95% 0-3%) |
| Voice transcript, correct | 136 | 0.0% (0/136; 95% 0-3%) | 0.0% (0/136; 95% 0-3%) | 0.0% (0/136; 95% 0-3%) |

By the accent hint given with the sentence (typed and voice together):

| Hint | Sentences | Any false alarm | False rewrites |
|---|---:|---:|---:|
| ar | 55 | 0 | 0 |
| hi | 54 | 0 | 0 |
| ml | 55 | 0 | 0 |
| none | 54 | 0 | 0 |
| tl | 54 | 0 | 0 |

## 2. Typed-text decode accuracy (headline)

Sentences typed by ear (respelled). *Exact* = the card's changes give the intended sentence; *asked* = a clarifying question offers the meant word (no silent guess); *left as typed* = nothing decoded and nothing asked (a miss; the misspelling stays visible in the text); *wrong rewrite* = the card changed something and the result is not the intended sentence (wrong-but-confident). (Left-as-typed was split from wrong rewrite after the first scoring run, because the first version lumped them.) **In-pack** = the respelling is one the accent packs are meant to cover; **out-of-pack** = a pattern they do not model (th->f, ee->i, h-dropping, ...), so this row is the honest limit.

| Respellings | Sentences | Exact | Asked | Exact or asked | Left as typed | Wrong rewrite (wrong-but-confident) |
|---|---:|---|---|---|---|---|
| In-pack | 125 | 92.0% (115/125; 95% 86-96%) | 3.2% (4/125; 95% 1-8%) | 95.2% (119/125; 95% 90-98%) | 2.4% (3/125; 95% 1-7%) | 2.4% (3/125; 95% 1-7%) |
| Out-of-pack | 61 | 0.0% (0/61; 95% 0-6%) | 0.0% (0/61; 95% 0-6%) | 0.0% (0/61; 95% 0-6%) | 100.0% (61/61; 95% 94-100%) | 0.0% (0/61; 95% 0-6%) |
| All | 186 | 61.8% (115/186; 95% 55-69%) | 2.2% (4/186; 95% 1-5%) | 64.0% (119/186; 95% 57-71%) | 34.4% (64/186; 95% 28-41%) | 1.6% (3/186; 95% 1-5%) |

By accent hint (in-pack and out-of-pack together):

| Hint | Sentences | Exact | Asked |
|---|---:|---:|---:|
| ar | 32 | 22 | 0 |
| hi | 43 | 26 | 1 |
| ml | 15 | 7 | 0 |
| none | 42 | 28 | 2 |
| tl | 54 | 32 | 1 |

## 3. Where / when / what / how-much extraction accuracy (headline)

For every slot that has a gold value: *correct*, *partial* (right but incomplete: "gate" for "main gate", "bring" for "bring trolley"), *empty* (nothing extracted: the safe failure) or *wrong* (a value that is not part of the gold: the dangerous one). (Partial was split from wrong after the first scoring run, because the first version counted every incomplete value as wrong.) *Spurious* = the slot had no gold value but the card filled it anyway (of all rows whose gold is empty).

| Rows | Slot | Gold present | Correct | Partial | Empty | Wrong | Spurious fills |
|---|---|---:|---|---:|---:|---|---|
| Typed correctly | where | 65 | 95.4% (62/65; 95% 87-98%) | 0 | 3 | 0.0% (0/65; 95% 0-6%) | 0.0% (0/71; 95% 0-5%) |
| Typed correctly | when | 60 | 88.3% (53/60; 95% 78-94%) | 0 | 7 | 0.0% (0/60; 95% 0-6%) | 0.0% (0/76; 95% 0-5%) |
| Typed correctly | what | 114 | 100.0% (114/114; 95% 97-100%) | 0 | 0 | 0.0% (0/114; 95% 0-3%) | 9.1% (2/22; 95% 3-28%) |
| Typed correctly | how_much | 21 | 100.0% (21/21; 95% 85-100%) | 0 | 0 | 0.0% (0/21; 95% 0-15%) | 0.0% (0/115; 95% 0-3%) |
| Voice transcript, correct | where | 65 | 95.4% (62/65; 95% 87-98%) | 0 | 3 | 0.0% (0/65; 95% 0-6%) | 0.0% (0/71; 95% 0-5%) |
| Voice transcript, correct | when | 60 | 88.3% (53/60; 95% 78-94%) | 0 | 7 | 0.0% (0/60; 95% 0-6%) | 0.0% (0/76; 95% 0-5%) |
| Voice transcript, correct | what | 114 | 100.0% (114/114; 95% 97-100%) | 0 | 0 | 0.0% (0/114; 95% 0-3%) | 9.1% (2/22; 95% 3-28%) |
| Voice transcript, correct | how_much | 21 | 100.0% (21/21; 95% 85-100%) | 0 | 0 | 0.0% (0/21; 95% 0-15%) | 0.0% (0/115; 95% 0-3%) |
| Typed by ear, in-pack | where | 65 | 95.4% (62/65; 95% 87-98%) | 0 | 3 | 0.0% (0/65; 95% 0-6%) | 0.0% (0/60; 95% 0-6%) |
| Typed by ear, in-pack | when | 51 | 84.3% (43/51; 95% 72-92%) | 0 | 8 | 0.0% (0/51; 95% 0-7%) | 0.0% (0/74; 95% 0-5%) |
| Typed by ear, in-pack | what | 104 | 96.2% (100/104; 95% 91-98%) | 0 | 4 | 0.0% (0/104; 95% 0-4%) | 9.5% (2/21; 95% 3-29%) |
| Typed by ear, in-pack | how_much | 20 | 100.0% (20/20; 95% 84-100%) | 0 | 0 | 0.0% (0/20; 95% 0-16%) | 0.0% (0/105; 95% 0-4%) |
| Typed by ear, out-of-pack | where | 30 | 40.0% (12/30; 95% 25-58%) | 4 | 12 | 6.7% (2/30; 95% 2-21%) | 0.0% (0/31; 95% 0-11%) |
| Typed by ear, out-of-pack | when | 31 | 58.1% (18/31; 95% 41-74%) | 2 | 11 | 0.0% (0/31; 95% 0-11%) | 0.0% (0/30; 95% 0-11%) |
| Typed by ear, out-of-pack | what | 48 | 62.5% (30/48; 95% 48-75%) | 1 | 15 | 4.2% (2/48; 95% 1-14%) | 7.7% (1/13; 95% 1-33%) |
| Typed by ear, out-of-pack | how_much | 7 | 14.3% (1/7; 95% 3-51%) | 0 | 6 | 0.0% (0/7; 95% 0-35%) | 0.0% (0/54; 95% 0-7%) |

Negation kept: 77 of 77 negated sentences still contain the negation in the plain English, or the card asked about a possible hidden negation (a negation must never be silently lost).

## 4. Voice safety net catch rate (secondary; read the labels)

* **Synthetic, author-written, tuned on it:** 125 of 188 risky words caught (66.5%: 36 rewritten, 89 asked), 4 wrong rewrites; false alarm 0 of 265 clean sentences. This set was used to set the margins, so it is an upper bound.
* **Held-out L2-ARCTIC (test only, Sarvam transcripts, D43): catch 0 of 72 risky words** (0 of 105 on the whatsapp-snr10 run). The errors in that data (coal -> cold, boat -> board) fall outside the where / when / what / amount / negation slots the net watches, so the net correctly does not look at them: the number says the net is not a general speech-to-text error fixer, and nothing about how it would do on workplace instructions.
* Whether real voice notes break critical-slot words at all is untested. The only real-audio evidence is D42: on clean and whatsapp-snr10 audio, numbers, times, places and negations came back right 48/57 and 47/57 times with 0 wrong real words (the rest not aligned or kept).

## 5. Every miss, listed

77 rows with a false alarm, a wrong-but-confident decode, or a wrong / spurious slot value (empty slots are counted above, not listed):

* `ev0065` [typed_clean, none] `you will get 1500 dirhams` -> what spurious: got 'get', gold ''
* `ev0118` [typed_clean, ml] `inshallah i come at five` -> what spurious: got 'come', gold ''
* `ev0201` [voice_clean, hi] `You will get 1500 dirhams.` -> what spurious: got 'get', gold ''
* `ev0254` [voice_clean, none] `Inshallah i come at five.` -> what spurious: got 'come', gold ''
* `ev0315` [typed_ear in-pack, tl] `te shipt starts at six` -> asked: Shift or shipt?
* `ev0317` [typed_ear in-pack, hi] `come nov` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0326` [typed_ear in-pack, tl] `te pine is two hundred dirhams` -> WRONG REWRITE: decoded as 'the pine is two hundred dirhams' (changes: te->the)
* `ev0329` [typed_ear in-pack, hi] `you vill get 1500 dirhams` -> what spurious: got 'get', gold ''
* `ev0331` [typed_ear in-pack, none] `bay fife hundred dirhams tomorrow` -> asked: Pay or bay?
* `ev0339` [typed_ear in-pack, ar] `nefer bark here` -> WRONG REWRITE: decoded as 'never bark here' (changes: nefer->never)
* `ev0343` [typed_ear in-pack, none] `don't bay fifty dirhams` -> asked: Pay or bay?
* `ev0349` [typed_ear in-pack, hi] `newer come to de site alone` -> asked: Never or newer?
* `ev0380` [typed_ear in-pack, none] `inshallah i come at fife` -> what spurious: got 'come', gold ''
* `ev0382` [typed_ear in-pack, tl] `mapi mushkila come tomorrow` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0386` [typed_ear in-pack, hi] `vallah i cannot come today` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0388` [typed_ear in-pack, hi] `dank you wery much` -> WRONG REWRITE: decoded as 'dank you very much' (changes: wery->very)
* `ev0398` [typed_ear out-of-pack, tl] `wait at the loadin bay` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0399` [typed_ear out-of-pack, ar] `mit me in the lobby` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0400` [typed_ear out-of-pack, hi] `park near the petrol istation` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0401` [typed_ear out-of-pack, tl] `brin the trolley to the warehouse` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0402` [typed_ear out-of-pack, none] `mit at the metro istation` -> LEFT AS TYPED (nothing decoded, nothing asked) ; where partial: got 'metro', gold 'metro station'
* `ev0403` [typed_ear out-of-pack, tl] `take the boxes to the istore rum` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0404` [typed_ear out-of-pack, none] `come to gate thri` -> LEFT AS TYPED (nothing decoded, nothing asked) ; where partial: got 'gate', gold 'gate 3'
* `ev0405` [typed_ear out-of-pack, ar] `go to flur twelve` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0406` [typed_ear out-of-pack, tl] `come to buildin five` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0407` [typed_ear out-of-pack, hi] `come to the parkin gate four` -> LEFT AS TYPED (nothing decoded, nothing asked) ; where wrong: got 'parkin gate 4', gold 'parking gate 4'
* `ev0408` [typed_ear out-of-pack, ml] `come to the ruftop` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0409` [typed_ear out-of-pack, ar] `go to the cantin` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0410` [typed_ear out-of-pack, ml] `mit me at the car wach` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0411` [typed_ear out-of-pack, ml] `brin the ladder to tower two` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0412` [typed_ear out-of-pack, ar] `istart work at seven in the mornin` -> LEFT AS TYPED (nothing decoded, nothing asked) ; when partial: got '7', gold '7 morning' ; what partial: got 'work', gold 'start work'
* `ev0413` [typed_ear out-of-pack, tl] `come before nun` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0414` [typed_ear out-of-pack, hi] `wait until mornin` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0415` [typed_ear out-of-pack, hi] `mit me on friday` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0416` [typed_ear out-of-pack, tl] `come by evenin` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0417` [typed_ear out-of-pack, hi] `the chift istarts at six` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0418` [typed_ear out-of-pack, tl] `the meetin is at free pm` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0419` [typed_ear out-of-pack, ar] `come after lunsh` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0420` [typed_ear out-of-pack, tl] `come next wik` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0421` [typed_ear out-of-pack, tl] `istart at nine` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0422` [typed_ear out-of-pack, none] `finich before midnight` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0423` [typed_ear out-of-pack, hi] `come this evenin` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0424` [typed_ear out-of-pack, tl] `come at nun` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0425` [typed_ear out-of-pack, ar] `the fine is two undred dirhams` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0426` [typed_ear out-of-pack, tl] `the taxi is fiftin dirhams` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0427` [typed_ear out-of-pack, tl] `pay five undred dirhams tomorrow` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0428` [typed_ear out-of-pack, none] `transfer free fousand dirhams` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0429` [typed_ear out-of-pack, hi] `the sharge is 12 dirhams` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0430` [typed_ear out-of-pack, tl] `send two undred aed today` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0431` [typed_ear out-of-pack, ml] `never park ere` -> LEFT AS TYPED (nothing decoded, nothing asked) ; what wrong: got 'never park ere', gold 'never park'
* `ev0432` [typed_ear out-of-pack, none] `don't brin the bags` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0433` [typed_ear out-of-pack, none] `do not open the dur` -> LEFT AS TYPED (nothing decoded, nothing asked) ; what wrong: got 'don't open dur', gold 'don't open door'
* `ev0434` [typed_ear out-of-pack, tl] `do not brin fud to the office` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0435` [typed_ear out-of-pack, hi] `come to the parkin gate free at five` -> LEFT AS TYPED (nothing decoded, nothing asked) ; where wrong: got 'parkin gate', gold 'parking gate 3'
* `ev0436` [typed_ear out-of-pack, ml] `mit me at the lobby tomorrow at nine` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0437` [typed_ear out-of-pack, hi] `brin the keys to the reception before nun` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0438` [typed_ear out-of-pack, tl] `wait at the loadin bay until six` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0439` [typed_ear out-of-pack, ar] `take the parcel to buildin nine on friday` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0440` [typed_ear out-of-pack, ml] `come to gate two tomorrow mornin` -> LEFT AS TYPED (nothing decoded, nothing asked) ; when partial: got 'tomorrow', gold 'tomorrow morning'
* `ev0441` [typed_ear out-of-pack, tl] `deliver the files to flur eight today` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0442` [typed_ear out-of-pack, none] `park the truck near tower free at nun` -> LEFT AS TYPED (nothing decoded, nothing asked) ; where partial: got 'tower', gold 'tower 3'
* `ev0443` [typed_ear out-of-pack, tl] `collect the bags from the istore rum at four` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0444` [typed_ear out-of-pack, tl] `brin the box to the site office today` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0445` [typed_ear out-of-pack, none] `pay two undred dirhams at the reception on monday` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0446` [typed_ear out-of-pack, ml] `mit me at the metro istation at six pm` -> LEFT AS TYPED (nothing decoded, nothing asked) ; where partial: got 'metro', gold 'metro station'
* `ev0447` [typed_ear out-of-pack, ar] `abibi wait at the lobby` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0448` [typed_ear out-of-pack, hi] `inchallah i come at five` -> LEFT AS TYPED (nothing decoded, nothing asked) ; what spurious: got 'come', gold ''
* `ev0449` [typed_ear out-of-pack, none] `yalla brin the bags to the villa` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0450` [typed_ear out-of-pack, ml] `mafi muchkila come tomorrow` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0451` [typed_ear out-of-pack, hi] `chway chway come to the gate` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0452` [typed_ear out-of-pack, tl] `the lift is not workin` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0453` [typed_ear out-of-pack, hi] `gud mornin sir` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0454` [typed_ear out-of-pack, hi] `fank you very mush` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0455` [typed_ear out-of-pack, none] `the fud is very gud` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0456` [typed_ear out-of-pack, none] `my phone is not workin` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0457` [typed_ear out-of-pack, ar] `i am appy today` -> LEFT AS TYPED (nothing decoded, nothing asked)
* `ev0458` [typed_ear out-of-pack, none] `the weafer is nice tomorrow` -> LEFT AS TYPED (nothing decoded, nothing asked)

Empty slots (nothing extracted although gold had a value): {'where': 21, 'when': 33, 'what': 19, 'how_much': 6}.

## 6. What this evaluation cannot show

* No real voice notes, no real typed messages (D42). All text is author-written; the by-ear respellings are generated by letter rules, real people vary far more.
* One author wrote the sentences and the gold, so the results reflect the author's own idea of the task. A different author would find different gaps.
* The in-pack rows use the same kinds of sound swaps the packs were built from, so the in-pack accuracy is optimistic; the out-of-pack rows show what happens outside them.
* No baseline comparison yet (a Gemini baseline on the same set is planned but not run: it costs API calls).

