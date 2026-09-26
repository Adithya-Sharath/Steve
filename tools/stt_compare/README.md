# STT reality test

**The question:** when a speech-to-text service hears accented English, does it keep the words that were *actually said* ("barking") or
silently "fix" them to what it expects ("parking")? The answer decides how Steve's decoder works (see DECISIONS D36 and PROGRESS Phase 1):

- If accent words **survive** in the transcript, the decoder can look for sound swaps (b for p) and rank the candidates.
- If the service already **"fixes"** them, the decoder must lean on phrases, on extracting the where / when / how much, and on asking a
  clarifying question when it is unsure.

This folder is tooling only. **You provide the recordings.** Nothing is sent to any service until you run `run.py --yes`.

## 1. Record 20 to 30 short sentences

Use your phone's voice recorder (anything that saves mp3, m4a, wav, ogg or webm works).

- One sentence per file, **3 to 15 seconds** (Sarvam's REST limit is 30 s). Speak at a normal pace, phone about 20 cm away.
- Read from [sentences_to_record.md](sentences_to_record.md) or use your own. Mix accents if you can: Arabic-accented English, Hindi/Urdu,
  Malayalam, Tagalog, Bangla, and so on. **Do not fake an accent.** Ask people who speak this way naturally, tell them what the recording is
  for, and get their OK. The audio goes to the speech providers you enable; do not record anything personal.
- Include the slang and local phrases (yalla, khalas, inshallah, "one minute") and a few sentences with numbers and times.
- Record **5 or 6 of them somewhere noisy** (outdoors, near traffic, a car) to see what noise does.
- Name the files `01.m4a`, `02.m4a`, ... and put them in `tools/stt_compare/recordings/`. That folder is gitignored, so the audio is never committed.

## 2. Fill in `truth.csv`

One row per recording, columns `file, spoken_as_heard, intended_meaning, accent, notes`:

| Column | What to write |
|---|---|
| `file` | the file name, e.g. `01.m4a` |
| `spoken_as_heard` | what you **actually hear the speaker say**, in ordinary English spelling, word for word. If they say "barking" for "parking", write `barking`. Do not fix it and do not write phonetics. If they said it clearly and correctly, write the correct word. |
| `intended_meaning` | what they **meant**, in plain English ("come to the parking") |
| `accent` | the speaker's background: `ar`, `hi`, `ml`, `tl`, `bn`, `ur`, or `other` |
| `notes` | optional: noisy / fast / the slang word / anything odd |

Example (the file names here are illustrative):

```csv
file,spoken_as_heard,intended_meaning,accent,notes
01.m4a,yalla habibi come to the barking gate tree,come on my friend come to the parking gate three,ar,slang + swaps
02.m4a,bring the bebsi from the fridge,bring the pepsi from the fridge,ar,
03.m4a,wery good come at fife,very good come at five,hi,noisy street
04.m4a,come to the parking now,come to the parking now,ml,said correctly: a control
```

Tips: include a few rows where the speaker said everything correctly (controls); they show whether a service *invents* errors. Two words
that differ only by a swap are the ideal test ("barking" / "parking"); a longer replaced phrase ("yalla habibi" / "come on my friend") is
scored as one phrase.

## 3. Run it

From the repo root, with the project's Python (`.venv`):

```powershell
.\.venv\Scripts\python.exe tools\stt_compare\run.py            # plan only: lists the calls, sends nothing
.\.venv\Scripts\python.exe tools\stt_compare\run.py --yes      # runs it (uses your Sarvam quota)
.\.venv\Scripts\python.exe tools\stt_compare\run.py --yes --quick   # only saaras:v3 transcribe + verbatim, en-IN
```

Keys come from `.env` (`SARVAM_API_KEY`, optionally `GEMINI_API_KEY`); they are never printed. Add `--providers sarvam,gemini` for a second
opinion. Answers are cached in `tools/stt_compare/.cache/`, so re-generating the report costs nothing.

Default Sarvam matrix (6 calls per recording): `saaras:v3` in `transcribe` and `verbatim` mode, each with `language_code` `en-IN` and
`unknown` (auto-detect), plus `saaras:v4` (no `mode`; the docs list `mode` for v3 only) with `en-IN` and `unknown`. Change it with
`--sarvam-matrix "saaras:v3|verbatim|en-IN,saaras:v4||unknown"` (fields are `model|mode|language`; an empty mode sends none).

## 4. Read the report

`tools/stt_compare/report.md` (and `results.json`) hold, for each provider, mode and language:

- **word error rate** against `spoken_as_heard` (what was actually said);
- how often the accent-influenced words were **kept as spoken**, **"fixed"** to the intended word, or **garbled** into something else;
- **latency** (mean, median, p95);
- a per-accent breakdown, examples of each outcome, and every recording with each provider's transcript.

Neither Sarvam nor Gemini documents word-level confidence or alternative hypotheses, so the report does not use them. Both files are gitignored
(they contain transcripts of your recordings); review them before deciding to commit anything.

## A 4th source: L2-ARCTIC Suitcase (spontaneous), `source=l2arctic-spont`

Real non-native English (Arabic and Hindi speakers) from `KoelLabs/L2ArcticSpontaneousSplit`, for evaluation only. **CC-BY-NC-4.0, gated**:
accept the terms on huggingface.co, put a token that can read gated repos in `.env` as `HF_TOKEN`, cite Zhao et al. (2018), do not commit any
audio or derived text (all of it lands in gitignored folders), and see DECISIONS D38 for the licence notes and the open questions (no word-level
transcript in the dataset, no scripted split in the repo).

```powershell
.\.venv\Scripts\python.exe -m pip install -r tools\requirements.txt
.\.venv\Scripts\python.exe tools\stt_compare\importers\l2arctic_spontaneous.py inspect
```

`inspect` prints the columns, whether a word-level transcript exists, the clip counts per accent and split, and the estimated speech-to-text usage
(clips x provider variants). It calls no speech provider and writes no audio.

## Phone-level test on L2-ARCTIC (no word gold needed)

`phone_eval.py` runs the spontaneous L2-ARCTIC clips through Sarvam and scores, for every sound the annotators heard differently, whether the
transcript kept the accented phone, fixed it to the canonical one, or garbled it (proxy through CMUdict; directional only; see DECISIONS D39).

```powershell
.\.venv\Scripts\python.exe tools\stt_compare\phone_eval.py --quick          # plan only: clips and calls, sends nothing
.\.venv\Scripts\python.exe tools\stt_compare\phone_eval.py --quick --yes    # 25 clips x 2 variants = 50 calls
```

Output (`report_l2arctic_spont.md`, `results_l2arctic_spont.json`), the clips (`recordings/l2arctic-spont/`) and the cache are gitignored.

## Word level for the spontaneous clips (no new calls)

`word_eval.py` reads the cached Sarvam transcripts and the sibling `KoelLabs/L2Arctic` recordings (gated, CC-BY-NC-4.0, accept its terms), locates each
clip inside its full recording, gets the words, finds the words heard differently and, when the heard form spells exactly one common English word,
checks whether the transcript wrote the intended word or the heard one. Output: `report_l2arctic_spont_words.md` (gitignored).

## Targeted scripted run (L2-ARCTIC, Arabic and Hindi)

`scripted_eval.py` picks the scripted utterances that contain at least one real-word swap and sends them to Sarvam in `transcribe` mode only.
It prints the utterance count, calls and an estimated cost first and sends nothing without `--yes`; it is paced under Sarvam's Starter limit
(60 requests per minute) and stops at once on a credit or quota looking error and after 3 errors in a row. The report (`report_l2arctic_scripted.md`,
gitignored) gives kept / fixed / other / not aligned for the swaps, per accent, next to the earlier spontaneous numbers, and lists every case where
Sarvam wrote a **different real word** than the intended one. Sarvam has no API for the credit balance: check it on the dashboard
(pricing when this was written: INR 30 per audio hour, https://www.sarvam.ai/api-pricing).

## Typed messages (WhatsApp, spelled by ear)

`typed_truth.csv` (columns `text_as_typed, intended_meaning, accent, source, notes`) is the truth file for the typed-text path of the decoder.
`typed_truth.py` loads and validates it and rejects rows that look like they contain a phone number, e-mail address or link, so anonymise real
messages first (`[NAME]`, `[PHONE]`). The committed rows are examples written by the developer (`source=synthetic-example`), not real messages.

## Other sources (inspect only, they print counts and estimated usage and stop)

- `importers/svarah.py inspect [--languages Hindi,Malayalam]`: Svarah (CC BY 4.0, gated); human transcripts, no phone annotation, so word error rate only.
- `importers/speech_accent_archive.py inspect --dir <folder>`: a local copy of the Speech Accent Archive (CC BY-NC-SA 4.0); everyone reads the same paragraph.
- `importers/l2arctic_spontaneous.py inspect`: see the section above.

## WhatsApp voice notes and other audio formats

Drop them into `recordings/` as they are. `.ogg` and `.opus` (what WhatsApp saves) and the other formats on Sarvam's list are sent unchanged;
`.oga`, `.3gp`, `.caf`, `.mka`, `.mov` and similar are converted with ffmpeg to 16 kHz mono WAV (in `.cache/converted/`, originals untouched).
Clips over 30 s trigger a warning (Sarvam's REST limit). Install ffmpeg or set `FFMPEG_DIR` if a conversion is needed.

## Adding another provider

Subclass `Provider` in `providers.py` (`available()`, `variants()`, `transcribe()`), raise `ProviderError` on failure (never include a key in
the message), and add it to `PROVIDERS`. Read the provider's current docs first.

## Tests

`python -m pytest tools/stt_compare -q` tests the scoring and the report with fake providers; no network and no audio are used.
