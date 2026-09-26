# Steve

> **"ok 👍" isn't understanding.**
> Steve checks that an important message actually got through. The reader explains it back in their own mix of languages, and Steve checks every dose, date and warning.

[![CI](https://github.com/Adithya-Sharath/Steve/actions/workflows/ci.yml/badge.svg)](https://github.com/Adithya-Sharath/Steve/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)
![Next.js](https://img.shields.io/badge/Next.js-16-000000)
![engine tests](https://img.shields.io/badge/engine%20tests-275%20passing-2e7d6b) ![api tests](https://img.shields.io/badge/api%20tests-228%20passing-2e7d6b)
![false understood](https://img.shields.io/badge/false%20%22understood%22-0%20%2F%20180-2e7d6b)
![API keys needed](https://img.shields.io/badge/API%20keys%20needed-0-0f6b6b)

**BitNBuild'26 · UAE regional round · AI/ML track** &nbsp;|&nbsp; [▶ Watch the 2-minute demo](VIDEO_LINK_HERE)

![Steve: the landing page](docs/screenshots/landing.png)

The false-"understood" badge is the engine on the 180 fact checks that were not understood within the baseline's subset (see [Evaluation](#testing-and-evaluation)); it is a development number, not a claim about real-world accuracy.

## About the name

Steve comes from the meme "it's me and you, and you and me, and your friend Steve": the friend in the middle who makes sure the two of you actually understood each other. The project started as "Samjha" (Hindi/Urdu for "understood?").

## The problem

- About **19%** of patients' answers about their own prescription labels were wrong, mostly dose (52%) and frequency (28%). [AAFP, 2007](https://www.aafp.org/pubs/afp/issues/2007/0615/p1851a.html)
- Teach-back cut comprehension deficits from **49% to 11.9%** in a 483-patient emergency-department study, but that study **excluded patients with language barriers**. [Int J Emerg Med](https://link.springer.com/article/10.1186/s12245-020-00306-9) · AHRQ recommends teach-back ([tool 5](https://www.ahrq.gov/health-literacy/improve/precautions/tool5.html))
- In the UAE, residents are about 38% Indian, 17% Pakistani, 7% Bangladeshi and 7% Filipino (GMI 2026), and many switch languages mid-sentence and write one language in another's script. [source](https://www.globalmediainsight.com/blog/uae-population-statistics/)

## What Steve does

1. **The sender writes** an important message (a dose, a visa deadline, a safety rule).
2. **Key facts are confirmed.** Facts are extracted into typed slots; the sender confirms or edits them.
3. **The reader explains it back**, by voice or text, in any language mix and any spelling, from a link or QR code with no login.
4. **The engine checks each fact:** `understood`, `wrong`, `missing`, `negated` or `unclear`, with the evidence and a plain reason.
5. **The sender sees what didn't land** and re-explains only that. **The reader is never shown a score**, only a thank-you.

Example: `randu gulika, food kazhinju, raavile vaikittu, oru week` against *2 tablets, after food, twice a day, 5 days, stop if rash* gives dose understood, timing understood, frequency understood (inferred from morning and evening, lower confidence), **duration wrong ("oru week" = 7 days, not 5)** and **rash warning missing**.

## How we read the problem statement

> *"Language tools learn one clean official version of a language, then meet people who switch tongues within a sentence, spell by ear, and write one language in another's script."*

| Workshop question | Our answer |
|---|---|
| **What did we cross out?** | ~~Translation and normalisation.~~ Most tools turn mixed language into "proper" English, which forces people back into the one clean version the statement criticises. Steve never translates the message or the reply; the reader's words are shown verbatim. |
| **What is the different moment?** | **The response**, not the message. Everyone works on how instructions are sent; nobody checks what happens when the reader answers a bare "ok". |
| **Who else is in the sentence?** | **The sender**, who cannot tell whether the message landed. Steve is built for them. |

## Why this isn't an AI wrapper

1. **An LLM is never the judge of a safety-critical fact.** Numbers, doses, frequencies, durations, dates, amounts and negations are decided by deterministic code we wrote and tested (275 engine tests).
2. **Zero keys needed.** LLMs are optional helpers: (a) suggesting facts the sender confirms, with a 10 s deadline and automatic fallback to the built-in extractor; (b) the evaluation baseline. Speech-to-text is optional; typed replies always work.
3. **The LLM-off test.** Run with `LLM_ENABLED=false`, or (as the operator, with `ADMIN_KEY` set and pasted once on `/admin`) flip the *LLM helper* switch in the nav. Compose, reply and check all keep working and the results page shows an "LLM off" badge. The switch is global, so it is admin-only and hidden from everyone else.
4. **A false "understood" is the worst error,** so low confidence, conflicts, concessives ("even if rash") and pasted-back messages end in `unclear`, `missing` or `negated`, never `understood`.
5. **Why not just ask an LLM?** LLMs score 5-12 F1 points worse on romanized Indian-language health messages than on native script, because of spelling noise ([arXiv 2512.10780](https://arxiv.org/html/2512.10780v1)). We measured a baseline (table below): on the same 180 not-understood facts, **our engine has 0 false "understood" and the Gemini baseline has 11**. In the interest of honesty: the baseline is slightly *more accurate* on plain accuracy (96.6% vs 95.9% once pasted-message rows are excluded), and our engine was tuned while reading this data, so the comparison favours us.
6. **Voice via Sarvam, verified live on an iPhone in Malayalam.** Speech-to-text is Sarvam Saaras in transliteration mode (romanized, **not** translated) behind a `SpeechToText` interface with a null fallback. The recording is sent for one request and never stored.

## Screenshots

| | | |
|---|---|---|
| ![Landing](docs/screenshots/landing.png) | ![Composer with confirmable fact chips](docs/screenshots/composer.png) | ![Live results, fact by fact](docs/screenshots/results.png) |
| **Landing.** The pitch, and a live example of message, voice reply and per-fact result. | **Composer.** Facts are extracted into chips the sender confirms; works with the LLM off. | **Results.** Cards flip from shimmer to status over SSE; the reader's words stay verbatim with evidence highlighted. |
| ![Reader page on a phone](docs/screenshots/reader-mobile.png) | ![A pasted-back reply is flagged](docs/screenshots/copied.png) | ![Evaluation page](docs/screenshots/eval.png) |
| **Reader (mobile).** Big record button, text fallback, no login and no score. | **Copied reply.** A reply that just parrots the message is flagged instead of counted as understood. | **Evaluation.** Metrics computed from `eval/results/*.json`, confusion matrix, error explorer. |

More: [results in dark mode](docs/screenshots/results-dark.png) · [recording with a mic-level halo](docs/screenshots/reader-recording.png) · [buttons: rest, hover, pressed](docs/screenshots/buttons.png) · [stats bento](docs/screenshots/landing-problem.png) · [how-it-works timeline](docs/screenshots/landing-how.png)

_Screenshots are real: Playwright against a production build (`next build && next start`)._

## Architecture

```mermaid
flowchart LR
  subgraph Reader["Reader (phone, no login)"]
    RP["Reader page /r/token<br/>voice or text"]
  end
  subgraph Web["Web (Next.js)"]
    SD["Sender dashboard<br/>composer, live results, follow-up"]
  end
  subgraph API["API (FastAPI + SQLite)"]
    X["Fact suggestion<br/>rules, or Gemini with a 10 s deadline<br/>then fallback to rules"]
    STT["Speech-to-text interface<br/>Sarvam or null"]
    E[["Engine (pure Python)<br/>clean, match by ear, negation,<br/>slots, compare, decide"]]
    SSE["SSE broker"]
  end
  SD -->|"message"| X
  X -->|"facts, sender confirms"| SD
  RP -->|"voice"| STT --> E
  RP -->|"text"| E
  E -->|"per-fact result"| DB[(SQLite)]
  E --> SSE -->|"live update"| SD
  X -.->|"optional"| G(("Gemini"))
  STT -.->|"optional"| S(("Sarvam"))
```

| Component | What it is |
|---|---|
| [`engine/`](engine/steve_engine) | Pure-Python checker: multilingual lexicon, by-ear matcher (exact, suffix, sound key, guarded fuzzy), per-language negation scope, slot fillers, exact comparison, copy detection. No network, no LLM. |
| [`api/`](api) | FastAPI and SQLModel on SQLite. Sender-key auth, reader-token endpoints, fact suggestion, speech-to-text interface, follow-up drafts, Server-Sent Events. |
| [`web/`](web) | Next.js App Router, TypeScript, Tailwind v4, shadcn/ui, Framer Motion, TanStack Query. Sender dashboard, mobile reader page, `/how-it-works`, `/eval`, `/demo`. |
| [`eval/`](eval) | Data generator, engine runner, Gemini baseline runner, metrics, README updater. |

Pipeline detail: [docs/architecture.md](docs/architecture.md).

## Quick start

No API keys are required for any of this.

**Windows (PowerShell)**

```powershell
git clone https://github.com/Adithya-Sharath/Steve.git
cd Steve
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e "engine[dev]" -e "api[dev]"
cd web; npm install; cd ..

# terminal 1: API
cd api; uvicorn app.main:app --port 8000

# terminal 2: web
cd web; npm run dev
```

**macOS / Linux**

```bash
git clone https://github.com/Adithya-Sharath/Steve.git
cd Steve
python3 -m venv .venv && source .venv/bin/activate
pip install -e "engine[dev]" -e "api[dev]"
(cd web && npm install)
make dev        # API on :8000 and web on :3000 together
```

Open <http://localhost:3000/demo> (it seeds four UAE scenarios) or <http://localhost:3000/app/new>. Prerequisites: Python 3.11+, Node 20+ (22 tested). Optional: `cp .env.example .env` to add keys. Docker: `docker compose up --build` (the images have not been built in our environment; the compose file is only validated).

## Configuration

Copy `.env.example` to `.env`. Everything is optional.

| Variable | Purpose |
|---|---|
| `LLM_ENABLED` | `true` lets Gemini *suggest* facts (needs `GEMINI_API_KEY`). The operator can also flip it at runtime with `ADMIN_KEY`. |
| `ADMIN_KEY` | Operator key (header `X-Admin-Key`, constant-time compare) for the **global** LLM switch, `POST /settings/llm`. Unset = the switch is disabled for everyone and `LLM_ENABLED` decides. Use 32+ random characters; paste it once on the unlinked `/admin` page to show the switch in the nav. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Optional. `GEMINI_MODEL` defaults to **`gemini-3.1-flash-lite`**: larger Gemini models allow only about 20 requests/day on a free key. Model ids: <https://ai.google.dev/gemini-api/docs/models>. |
| `LLM_TIMEOUT_SECONDS`, `LLM_COOLDOWN_SECONDS` | Fact suggestion has a hard **10 s** deadline (default; the Gemini API itself rejects anything under 10 s), then the built-in extractor answers. After a failure the LLM is skipped for 60 s (15 min after a daily-quota error), so "Find key facts" never hangs. |
| `SARVAM_API_KEY`, `STT_ENABLED` | Optional voice replies (Malayalam, Hindi, English). `STT_ENABLED` defaults to `true` but only takes effect when a key is set. Arabizi and Taglish are typed for now. |
| `DATABASE_URL` | Default `sqlite:///./steve.db` |
| `STEVE_DATA_DIR`, `STEVE_EVAL_DIR` | Override where the API reads scenario data and evaluation results (used by the Docker image). |
| `PUBLIC_WEB_URL`, `CORS_ORIGINS` | Where the web app lives (used in reader links and CORS). |
| `TRUST_PROXY`, `TRUSTED_PROXIES` | Default `false`. Set `true` only behind a reverse proxy or tunnel to read the client IP from `CF-Connecting-IP` / the right-most untrusted `X-Forwarded-For` entry (`TRUSTED_PROXIES`: extra hops to skip, IPs/CIDRs). When false those headers are ignored, because clients can forge them. |
| `UNCLEAR_THRESHOLD` | Confidence below this becomes `unclear` (default 0.6). |
| `RL_MESSAGES_PER_MIN`, `RL_MESSAGES_PER_DAY`, `RL_MESSAGES_PER_SENDER_DAY` | `POST /messages` limits: per IP per minute (10) and per day (100), and per sender key per day (30). |
| `REPLY_RATE_LIMIT`, `REPLY_CAP_PER_MESSAGE` | Replies: maximum per minute from one client to one reader link (12), and a hard cap of stored replies per message (30). |
| `RL_CHECK_PER_MIN`, `RL_SEED_PER_MIN`, `RL_DEFAULT_PER_MIN` | `/check` and `/analyze` (60/min per IP each), `/demo/seed` (5/min), every other route (120/min per IP). A value of 0 turns a rule off; blocked requests get `429` with `Retry-After`. |
| `LLM_DAILY_CAP`, `STT_DAILY_CAP` | Global calls per UTC day to Gemini (200) and Sarvam (300). Over the cap the built-in extractor answers ("daily AI limit reached") and voice replies ask the reader to type. `/health` shows what is left. `0` blocks the service, negative means unlimited. |
| `MAX_BODY_BYTES` | Requests larger than this are refused with 413 (default 5 MB). |
| `STEVE_EMBEDDINGS` | Set to `1` to enable the optional embedding fallback for condition facts (needs `sentence-transformers`; off until calibrated). |
| `NEXT_PUBLIC_API_URL` | Web to API base URL (default `http://localhost:8000`); baked in at build time. |

**Phone testing:** the microphone needs HTTPS or localhost. A free Cloudflare tunnel for the web app and one for the API works well: set `PUBLIC_WEB_URL` and `CORS_ORIGINS` to the web tunnel address, `NEXT_PUBLIC_API_URL` to the API tunnel address, **`TRUST_PROXY=true`** (the tunnel sends `CF-Connecting-IP`, so each visitor gets their own rate-limit bucket instead of sharing the tunnel's address), then rebuild the web app. Do not also expose port 8000 to your network while `TRUST_PROXY=true`.
**Deploy:** web on Vercel (`NEXT_PUBLIC_API_URL` = your API URL); API on Render, Railway or Fly using `api/Dockerfile` (build context = repo root), with `PUBLIC_WEB_URL` and `CORS_ORIGINS` set to the web URL and a volume for SQLite.

## Testing and evaluation

**Tests:** `make test` (engine 275 + API 228), `make lint`; without `make`, `scripts/test.ps1` or the commands in [CONTRIBUTING.md](CONTRIBUTING.md). CI runs them on every push.
**Evaluation:** `make eval` (works without a Gemini key; the baseline is then skipped and clearly marked "not run").

Methodology: 15 messages with gold facts (`data/messages.json`) times replies with per-fact gold labels (`data/replies.csv`): **hand-written** replies (a development set and a small held-out set) plus **synthetic** variants expanded from templates (`eval/generate.py`: swapped numbers, spelling variants, word order, dropped facts, negation flips, typos), always marked `synthetic=true` and reported separately. Metrics (`eval/metrics.py`): fact-level accuracy, the **false "understood" rate** (gold is wrong, missing or negated but predicted understood), per-language and per-type breakdowns, a confusion matrix and the baseline's self-consistency.

<!-- EVAL:START -->
_Generated by `eval/update_readme.py` from `eval/results/latest.json` on 2026-09-26T08:16:36+00:00. 2268 labelled fact checks across 561 replies (114 hand-written, 447 synthetic)._

| System / slice | Fact checks | Accuracy | False “understood” |
|---|---:|---:|---:|
| **Our engine · all** | 2268 | 96.9% | 0/921 (0.0%) |
| Our engine · handwritten | 332 | 98.8% | 0/69 (0.0%) |
| Our engine · held-out | 175 | 89.1% | 0/41 (0.0%) |
| Our engine · synthetic | 1761 | 97.3% | 0/811 (0.0%) |
| Our engine · arabizi | 402 | 96.0% | 0/188 (0.0%) |
| Our engine · english | 518 | 98.6% | 0/209 (0.0%) |
| Our engine · hinglish | 496 | 95.6% | 0/193 (0.0%) |
| Our engine · manglish | 426 | 97.2% | 0/160 (0.0%) |
| Our engine · taglish | 426 | 96.7% | 0/171 (0.0%) |
| **Gemini baseline** (same replies, 3 runs, majority vote) | 665 | 94.6% | 11/180 (6.1%) |
| Our engine on the baseline's exact subset | 665 | 95.9% | 0/180 (0.0%) |
| Baseline, excluding 14 pasted-message rows | 651 | 96.6% | 11/180 (6.1%) |
| Our engine, same rows | 651 | 95.9% | 0/180 (0.0%) |

Baseline self-consistency across runs: **100.0%** (our engine: 100%, deterministic). model: gemini-3.1-flash-lite, evaluated on 154 replies (all hand-written + a synthetic sample)

**Caveats** (please read):
- Synthetic variants are generated from team-written templates that reuse vocabulary the lexicon knows, so they overestimate real-world accuracy. Compare the hand-written row.
- The hand-written seed replies were drafted by the developer/assistant, not native speakers, and the engine was iterated while looking at this set. Treat all numbers as development-set numbers.
- Lexicon entries for non-English languages are unverified until native speakers review LEXICON_REVIEW.md.
- Gold labels for synthetic rows come from construction; for hand-written rows from a human reading the reply. Some real-world replies are genuinely ambiguous.
- COMPARISON FAVOURS US: the engine was developed while reading this data; the baseline (gemini-3.1-flash-lite) is one zero-shot prompt that saw none of it. It covers 665 fact checks (154 replies: all hand-written plus a synthetic sample), 3 runs each, majority vote. A stronger model may score higher.
- Where the baseline wins: excluding the 14 pasted-message rows (gold unclear; that rule is ours and was not in its prompt), on the same 651 checks the baseline is MORE accurate than our engine (96.6% vs 95.9%). Our advantage is on false 'understood' (0/180 vs 11/180), not on raw accuracy.
- The baseline agreed with itself on every item across 3 runs, so consistency is NOT an advantage we can claim over this model (our engine is deterministic by construction).
<!-- EVAL:END -->

**Read this honestly.** The engine was developed while reading this data, and the synthetic replies reuse vocabulary the lexicon already knows, so these are *development* numbers, not a claim about real-world accuracy. The held-out set's first blind run (before any fix) scored **87.4%** accuracy with 0 false "understood" out of 41; we then fixed what it exposed, so it is no longer blind ([DECISIONS D10](DECISIONS.md)). "0 false understood" on small denominators is **not** evidence of 0%. The known residual risk is a misspelled negation word we do not recognise. We need real replies from real speakers: see [CONTRIBUTING.md](CONTRIBUTING.md#add-real-replies-most-useful).

## Project structure

```
engine/   pure-Python checker: lexicon.yaml, matcher, slots, negation, compare, check_reply()   (+275 tests)
api/      FastAPI: routes, SQLModel db, extractor, STT interface, follow-up drafts, SSE           (+228 tests)
web/      Next.js app: landing, /app, /app/new, /app/m/[id], /r/[token], /eval, /how-it-works, /demo
data/     scenarios.json (demo and regression tests), messages.json + replies.csv (eval gold data)
eval/     generate.py, run_engine.py, run_baseline.py, metrics.py, update_readme.py, results/
docs/     architecture.md, demo-script.md, build-prompt.md, screenshots/, README.md (index)
scripts/  Windows helpers: dev.ps1, test.ps1, eval.ps1
.github/  CI workflow, issue and pull-request templates
DECISIONS.md, PROGRESS.md, CLAUDE.md, LEXICON_REVIEW.md, CONTRIBUTING.md, SECURITY.md, LICENSE
docker-compose.yml, Makefile, .env.example
```

## Roadmap

- **A call plugin.** The same engine as a channel for phone calls: a turn-based IVR where the instruction plays, the reader explains it back after the beep, consent comes first and audio is never stored.
- **Native-speaker lexicon review** and a real blind test set, so the numbers stop being development numbers.
- **More languages via language packs:** a lexicon block plus test data, no retraining. Arabic and Tagalog voice come with them.
- **A B2B dashboard for clinics and pharmacies** with message-level results only (no per-worker scoring).

Also planned: WhatsApp Business delivery (today: copy and QR), Arabic-script and Devanagari input, larger numbers and ordinals per language, and calibrating the embedding fallback for conditions.

## Limitations and ethics

- **Not medical advice.** Steve checks whether a message was understood; the sender decides what to do. It is not a clinical device.
- **Lexicon coverage is small and unverified.** Five languages, about 300 headwords, every non-English entry awaiting native-speaker review. Unknown words produce `missing` or `unclear`, never a guess. Numbers above ten are only recognised as digits.
- **Synthetic and self-authored eval data** (see Testing and evaluation). Baseline numbers appear only if the baseline actually ran.
- **Known weak spots:** misspelled negation words; replies that use an unlisted word for a fact ("pani" for fever, "saade barah baje" for 12:30); an unnumbered "form" or "bottle" is counted as one; two unmatched facts of the same kind can only be `unclear`.
- **Privacy:** audio is held in memory for a single speech-to-text request and never stored; the reader never sees results; replies are stored as text. Sender endpoints require a per-browser **sender key** (sent as `X-Sender-Key`, stored server-side only as a hash); readers need only their link. Trade-off: the key lives in one browser, so clearing site data or switching device loses access to those messages. The global LLM switch is admin-only (`ADMIN_KEY`); a sender key cannot flip it. See [SECURITY.md](SECURITY.md).
- **Abuse and cost controls are a brake, not a shield.** Rate limits, daily Gemini/Sarvam caps and the request-size cap live in the API process (a restart or several workers weaken them) and do not stop a determined attacker with many IPs; the daily caps are not billing, so also set a spending limit with each provider. The Gemini fact extractor treats the sender's message as data and its answer is validated server-side (at most 12 facts, sane ranges, invalid facts dropped), but a validator cannot tell a plausible wrong fact from a right one: the sender always confirms the facts, and the engine, not the model, judges replies. An admin key pasted into a browser lives in its local storage, so use it on a demo machine.
- **Voice** uses Sarvam (Indian languages); Gulf Arabic and Tagalog voice are not supported yet.
- **Closest competitor: Hippocratic AI**, whose AI voice agents make post-discharge calls (active in the UAE via Burjeel). We differ: Steve is a *checking layer any sender (human or AI) can use*, focused on romanized code-mixed replies, with exact checks on numbers.

## Team

- NAME_1 — role
- NAME_2 — role
- NAME_3 — role

## License

MIT, see [LICENSE](LICENSE).
