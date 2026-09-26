# Security

Steve is a hackathon project and has not had a formal security audit. This page says what it does to limit abuse and where the limits are.

## How keys are handled

- All keys (`GEMINI_API_KEY`, `SARVAM_API_KEY`, `ADMIN_KEY`, `TWILIO_AUTH_TOKEN`, `TWILIO_ACCOUNT_SID`, `WORKER_HASH_SECRET`) are read from environment variables or a local `.env` file. `.env` is gitignored and must never be committed. `.env.example` lists every variable with no values.
- Every key is optional. With none set, the whole product works: the engine is deterministic and the LLM and speech-to-text are only optional helpers.
- Keys never reach the browser, with one deliberate exception: the operator can paste `ADMIN_KEY` into the unlinked `/admin` page, which stores it in that browser's `localStorage` (see below).
- If a key is ever pasted into a chat, an issue or a log, rotate it.
- Logs: the API masks `?key=` in access-log lines, and redacts configured secrets from error logs and tracebacks. A reverse proxy in front of the API keeps its own access log, which will contain that URL.

## Who can do what

| Actor | Can | Cannot |
|---|---|---|
| **Reader** (has a link) | Read that one message and post replies to it | See any result, score or other message |
| **Sender** (self-issued `X-Sender-Key`) | Create messages, read and follow up on the messages that key created | Read anyone else's messages; change global settings |
| **Worker** (Decode; self-issued `X-Worker-Key: wk_...`) | Decode text and voice notes, answer their own clarifying questions | See anyone else's questions or results; nothing about a worker is stored |
| **WhatsApp user** (a signed Twilio webhook) | Message the Steve number and get text replies | Anything else; unsigned requests do nothing |
| **Operator** (`ADMIN_KEY`, header `X-Admin-Key`) | Switch the optional LLM helper on or off for everyone | (Nothing else is admin-gated) |

- **Sender key:** generated in the browser (`sk_...`, kept in local storage). The server stores only its SHA-256 hash, and a message belongs to the key that created it. It is a capability, not a password: it lives in one browser, so clearing site data or switching device loses access to those messages. Anyone can mint a new one, so it proves ownership of a message, never trust.
- **Reader links** (`/r/{token}`) are open to anyone holding the link, so treat them like private links.
- **Admin key:** the global LLM switch changes behaviour for every user, so a self-issued sender key is not enough. Set `ADMIN_KEY` (32+ random characters) to enable it; the comparison is constant-time. If `ADMIN_KEY` is unset the endpoint answers 403 to everyone and the switch simply follows `LLM_ENABLED`. The web app shows the switch only when the server reports `admin_toggle_available` **and** the browser holds the key. That key sits in `localStorage`, readable by any script on that origin, so use this on a demo machine, not as a login system.

## Abuse and cost controls (API)

- **Rate limits** (in-memory sliding windows; friendly `429` with `Retry-After`; a value of 0 turns a rule off): `POST /messages` 10/min and 100/day per IP and 30/day per sender key; replies 12/min per link and IP plus a hard cap of 30 replies per message; `/check` and `/analyze` 60/min per IP; `/demo/seed` 5/min; everything else 120/min per IP. All are env-configurable (see the README configuration table).
- **Real client IP:** `X-Forwarded-For` and `CF-Connecting-IP` are client-writable, so they are ignored unless `TRUST_PROXY=true`. With it on, the address is `CF-Connecting-IP` if present, otherwise the right-most untrusted `X-Forwarded-For` entry (`TRUSTED_PROXIES` lists extra hops to skip). Turn it on only when a proxy really sits in front of the API and the API is not reachable directly, otherwise a client can pick its own rate-limit bucket.
- **Daily spending caps:** `LLM_DAILY_CAP` (default 200 Gemini calls) and `STT_DAILY_CAP` (default 300 Sarvam calls) per UTC day, across all users. Over the cap the composer falls back to the built-in extractor ("daily AI limit reached") and voice replies ask the reader to type. `/health` shows the remaining counts (numbers only). Counters live in the API process and reset on restart, so also set a spending limit with each provider.
- **Prompt injection:** the sender's message goes to Gemini as delimited data with a system instruction that forbids following instructions inside it, and the reply is validated on the server (at most 12 facts, allowed types, sane numeric ranges, labels at most 80 characters, control characters stripped, invalid facts dropped, nothing valid means fallback to the built-in extractor). The LLM only ever *suggests* facts that the sender confirms; it never sees replies and never decides a verdict.
- **Decode limits:** `POST /decode` 30 per minute and 500 per day per IP and 200 per day per worker key; voice decodes also spend `STT_DAILY_CAP`; translation calls `TRANSLATE_DAILY_CAP` (Gemini calls also `LLM_DAILY_CAP`); audio at most 4 MB and (WAV/Ogg) 30 s; WhatsApp 20 messages per hour and 100 per day per number, one "too many messages" notice an hour, and the webhook has its own per-IP limit. All in `.env.example`.
- **CORS:** `CORS_ORIGINS` (a list, or `*`) decides which sites may call the API from a browser; credentials are never allowed (there are no cookies), and `CORS_ALLOW_LOCALHOST=false` removes the built-in localhost rule.
- **Basics:** `nosniff`, `Referrer-Policy: no-referrer` and a minimal CSP on JSON responses; request bodies over 5 MB are refused (413); unexpected errors return a generic 500 with no stack trace, path or key.

Limits of all of the above: state is per process (a restart or several workers weaken the counters), it slows a determined attacker with many IPs rather than stopping them, and it is not DDoS protection. Put the API behind a real edge (Cloudflare, a platform rate limiter) if it faces the public for long.

## Audio and data

- Audio is held in memory for a single speech-to-text request and is **never stored**. Only the resulting transcript is saved with the reply.
- Replies are stored as text in the API's SQLite database. The reader is never shown results.
- At runtime the LLM (if enabled) only sees the sender's message text, to suggest facts the sender then confirms. It never sees replies. (The offline evaluation baseline sends only our own test replies, never real ones.)

## Decode: workers, WhatsApp, translation and what is stored

- **Worker key.** The web app and any other front end send `X-Worker-Key: wk_<24-128 URL-safe characters>`, generated on the device. It is a capability, not a password: only its SHA-256 is used (for the per-worker limit and to tie a clarifying question to its asker), and **nothing about the worker is stored**. A sender key is not accepted as a worker key.
- **Audio and message text are never stored and never logged.** Audio is held in memory for one speech-to-text call and dropped (uploads are kept in memory: Starlette's multipart spool to disk is disabled and a test fails if it rolls). The text of a decode is not written anywhere. Tests capture logs at DEBUG on the normal, validation-error, translation-failure, send-failure and server-error paths and assert that no text, transcript or phone number appears.
- **Clarifying questions** keep the ORIGINAL TEXT (never audio) and the answers in memory only, keyed by an opaque id and by the worker, for 10 minutes after the last answer (at most 10 open per worker, 5,000 in all); the id is deleted when the last question is answered; a wrong worker, an expired id and an unknown id all answer the same 404, so ids cannot be probed.
- **Translation** sends only the settled English card (never the worker's original text) to Sarvam or Gemini. Numbers, times, amounts, places and question options are replaced by placeholders first and a check requires every number to come back unchanged, or the translation is dropped. Translations are cached **in memory** for 15 minutes by content hash and never persisted. The check cannot see a lost negation (see the README).
- **WhatsApp (Twilio).** Every webhook must carry a valid `X-Twilio-Signature` (HMAC-SHA1 over the exact configured URL and the sorted parameters, compared in constant time and tested against Twilio's documented example); anything else gets 403 and does nothing. The endpoint is off (404) unless `WHATSAPP_ENABLED=true` and needs `WORKER_HASH_SECRET` (503 without). Phone numbers are hashed at once with HMAC-SHA256 keyed by `WORKER_HASH_SECRET` and never stored, logged or shown again: the database holds only that hash, the language chosen and two anonymous counters (a test dumps every table after a conversation). Steve only answers messages it receives (never first, never into groups). Voice notes are downloaded with Twilio basic auth, capped at 4 MB and 30 s, and dropped from memory after the speech-to-text call. **Twilio keeps its own logs and media**; Steve does not delete them (see `docs/whatsapp-setup.md`). Changing `WORKER_HASH_SECRET` makes every returning user new again.
- **The demo endpoints** (`GET /decode/health`, `GET /decode/examples`) need no key and expose no secrets (a test plants secrets and asserts they never appear).
- **What we have not done:** a formal audit, load testing, DDoS protection, per-user accounts, or deleting media on Twilio's side. The Decode limits, like the older ones, live in the API process.

## Local demo through Cloudflare tunnels

Set `TRUST_PROXY=true` so each visitor is identified by `CF-Connecting-IP` instead of all sharing the tunnel's address, and do not also expose port 8000 on your network. Set `ADMIN_KEY` if you want the LLM switch, and paste it once on `/admin`. Tunnel addresses are public while they run.

## Reporting a problem

Please report security issues privately by opening a GitHub security advisory on this repository (Security tab, "Report a vulnerability"), or contact the maintainers listed in the README. Do not include real keys or personal data in a report. We will acknowledge within a few days.
