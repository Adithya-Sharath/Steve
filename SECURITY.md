# Security

## How keys are handled

- All keys (`GEMINI_API_KEY`, `SARVAM_API_KEY`) are read from environment variables or a local `.env` file. `.env` is gitignored and must never be committed. `.env.example` lists every variable with no values.
- Every key is optional. With none set, the whole product works: the engine is deterministic and the LLM and speech-to-text are only optional helpers.
- Keys never reach the browser. The web app talks only to our API.
- If a key is ever pasted into a chat, an issue or a log, rotate it.

## Audio and data

- Audio is held in memory for a single speech-to-text request and is **never stored**. Only the resulting transcript is saved with the reply.
- Replies are stored as text in the API's SQLite database. The reader is never shown results.
- At runtime the LLM (if enabled) only sees the sender's message text, to suggest facts the sender then confirms. It never sees replies and never decides a verdict. (The offline evaluation baseline sends only our own test replies, never real ones.)

## The sender-key model

- Sender endpoints require a per-browser **sender key** (`X-Sender-Key: sk_...`, generated in the browser and kept in local storage). The server stores only its SHA-256 hash.
- A message belongs to the key that created it; another browser gets a 403 for it.
- Reader endpoints (`/r/{token}`) are open to anyone holding the reader link, so treat reader links like private links.
- Trade-off: the key lives in one browser. Clearing site data or switching device loses access to those messages. The runtime LLM switch is global, so on a public deployment set `LLM_ENABLED` in the environment.

## Reporting a problem

Please report security issues privately by opening a GitHub security advisory on this repository (Security tab, "Report a vulnerability"), or contact the maintainers listed in the README. Do not include real keys or personal data in a report. We will acknowledge within a few days.

This is a hackathon project and has not had a formal security audit.
