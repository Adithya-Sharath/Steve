# Gemini baseline vs the engine on the Decode v2 set (D49)

Model `gemini-3.1-flash-lite` (lite, temperature 0), prompt "rewrite in plain neutral English and extract where/when/what/how much as JSON", the same accent hint as the engine, **at most 253 Gemini calls in total** (243 answered on the first pass, the 2 others retried; every row had at most 4 attempts) (owner budget 300; answers are cached, so a rerun costs nothing), 245 of 245 rows answered. Data: `data/decode/eval_v2.csv`, **synthetic, one author, gold written by the same author** (D44); the engine column is the CURRENT engine, which has had two small fixes since its own first scoring of this set (clock minutes, adverbs as objects), so read the engine column as **contaminated on v2**; the fresh first run is in `decode_eval_v2_first_run.md`. Rows with glossary phrases are left out of the rewrite metrics (replacing "yalla" is right for both). No real workers, no real messages (D42).

| Metric | Engine (current) | Gemini (lite) |
|---|---|---|
| False rewrite on correctly written sentences without glossary phrases (lower is better) | 1.5% (2/136; 95% 0-5%) | 30.9% (42/136; 95% 24-39%) |
| Typed by ear, in-pack: intended sentence recovered | 93.7% (59/63; 95% 85-98%) | 81.0% (51/63; 95% 70-89%) |
| Typed by ear, in-pack: asked instead of guessing | 4.8% (3/63; 95% 2-13%) | n/a (cannot ask) |
| Typed by ear, in-pack: left as typed | 0.0% (0/63; 95% 0-6%) | 0.0% (0/63; 95% 0-6%) |
| Typed by ear, in-pack: rewritten so the wording differs from the intended sentence (for Gemini this includes harmless paraphrase) | 1.6% (1/63; 95% 0-8%) | 19.0% (12/63; 95% 11-30%) |
| Typed by ear, out-of-pack: intended sentence recovered | 0.0% (0/31; 95% 0-11%) | 74.2% (23/31; 95% 57-86%) |
| Typed by ear, out-of-pack: asked instead of guessing | 0.0% (0/31; 95% 0-11%) | n/a (cannot ask) |
| Typed by ear, out-of-pack: left as typed | 100.0% (31/31; 95% 89-100%) | 0.0% (0/31; 95% 0-11%) |
| Typed by ear, out-of-pack: rewritten so the wording differs from the intended sentence (for Gemini this includes harmless paraphrase) | 0.0% (0/31; 95% 0-11%) | 25.8% (8/31; 95% 14-43%) |
| where: correct | 81.5% (101/124; 95% 74-87%) | 91.1% (113/124; 95% 85-95%) |
| where: wrong value (lower is better) | 1.6% (2/124; 95% 0-6%) | 8.1% (10/124; 95% 4-14%) |
| where: spurious fill where the gold has none (lower is better) | 2.5% (3/121; 95% 1-7%) | 9.1% (11/121; 95% 5-16%) |
| when: correct | 86.4% (89/103; 95% 78-92%) | 88.3% (91/103; 95% 81-93%) |
| when: wrong value (lower is better) | 0.0% (0/103; 95% 0-4%) | 11.7% (12/103; 95% 7-19%) |
| when: spurious fill where the gold has none (lower is better) | 0.0% (0/142; 95% 0-3%) | 2.8% (4/142; 95% 1-7%) |
| what: correct | 93.6% (191/204; 95% 89-96%) | 53.4% (109/204; 95% 47-60%) |
| what: wrong value (lower is better) | 1.0% (2/204; 95% 0-4%) | 46.6% (95/204; 95% 40-53%) |
| what: spurious fill where the gold has none (lower is better) | 0.0% (0/41; 95% 0-9%) | 26.8% (11/41; 95% 16-42%) |
| how_much: correct | 84.8% (28/33; 95% 69-93%) | 100.0% (33/33; 95% 90-100%) |
| how_much: wrong value (lower is better) | 3.0% (1/33; 95% 1-15%) | 0.0% (0/33; 95% 0-10%) |
| how_much: spurious fill where the gold has none (lower is better) | 0.0% (0/212; 95% 0-2%) | 0.0% (0/212; 95% 0-2%) |
| Negation lost (of 41 negated rows; lower is better) | 0.0% (0/41; 95% 0-9%) | 0.0% (0/41; 95% 0-9%) |

**How to read it.** Gemini can rewrite any spelling, so it can beat the engine wherever the respelling is outside the engine's accent packs; it has no way to ask, no list of things it must never rewrite silently, and it is free to paraphrase. The engine is the reverse: narrow, deterministic, asks when unsure. The rows to compare are the false rewrites, the wrong values and the lost negations (silent failures), and the recovered-sentence rows (where Gemini is expected to win on out-of-pack respellings).

**Where Gemini wins, plainly:** it recovers **74.2% of the respellings the engine's accent packs do not model (the engine: 0%, it leaves them as typed)** and **81.0% of the in-pack ones (engine 93.7%)**, and it extracts `where` (91.1% vs 81.5%) and `how much` (100% vs 84.8%) better on this mixed set. **Where the engine wins:** it almost never rewrites a correct sentence (1.5% vs 30.9%), never returned a wrong `when` (0 vs 12), and it can ask instead of guessing (Gemini cannot).

**Read the comparison with these limits.** (1) The gold labels were written around the engine's conventions (`what` = the verb plus its noun object, `where` = the place phrase), so Gemini's fuller phrases ("Come to the main gate" for `what` = "come") are counted as wrong `what` values (47% of rows): that says the conventions differ, not that its instructions were wrong. (2) "Wording differs" counts any paraphrase ("do not" for "don't", a capital letter and a full stop are ignored, but a reordered sentence is not), so the false-rewrite and wrong-rewrite rows overstate real damage for Gemini; the silent failures that matter, a wrong `when` and a lost negation, are the rows to trust (Gemini: 12 wrong `when` values, 0 lost negations; engine: 0 and 0). (3) Two rows got no answer from Gemini (243 of 245 answered). (4) One author wrote the sentences, the gold and the respellings; the engine was built by the same team that wrote them. (5) A lite model at temperature 0 with one prompt that saw none of this data; a stronger model or a tuned prompt may do better.

