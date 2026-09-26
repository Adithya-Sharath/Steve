# WhatsApp setup (Twilio sandbox)

Steve answers WhatsApp messages through the **Twilio WhatsApp Sandbox**: text replies only, only to people who message it first. Nothing in the code base has sent a live
WhatsApp message yet: the flow was tested with mocked Twilio calls (`api/tests/test_whatsapp.py`). These are the steps for you, in order. Facts about Twilio come from
Twilio's own documentation (read 2026-09-26); if the console looks different, trust the console.

## 1. Create the Twilio account and open the sandbox

1. Sign up at <https://www.twilio.com/try-twilio> (a trial account is enough). Verify your own phone number when asked.
2. In the Twilio Console open **Messaging → Try it out → Send a WhatsApp message** (the WhatsApp Sandbox page).
3. The sandbox sends from a shared number, **+1 415 523 8886**, and shows your **join code** (`join <two-words>`).
4. From your phone, open WhatsApp and send `join <your-code>` to +1 415 523 8886. Twilio confirms in the chat. Every person who wants to try Steve must do this once;
   **a sandbox session expires three days after joining** (join again). The sandbox is for testing only, not for production.

## 2. Find three values

In the Console home page ("Account Info"): **Account SID** (starts with `AC`) and **Auth Token** (click to reveal). Generate the third yourself:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"      # this is WORKER_HASH_SECRET
```

`WORKER_HASH_SECRET` keys the hash of every phone number (HMAC-SHA256). Keep it secret and **never change it**: changing it makes every returning user a stranger again and they
would see the language picker once more. Do not paste these values into a chat or an issue; if you do, rotate them.

## 3. Run the API with WhatsApp switched on

In the repo's `.env` (never committed):

```
WHATSAPP_ENABLED=true
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token
WORKER_HASH_SECRET=the-long-random-string-from-step-2
WHATSAPP_WEBHOOK_URL=https://YOUR-PUBLIC-URL/whatsapp/webhook      # see step 4: must be EXACTLY the URL you give Twilio
TRUST_PROXY=true                                                     # when the API sits behind a tunnel or proxy
SARVAM_API_KEY=...        # optional: voice notes and translation into ml/hi/ur/bn
GEMINI_API_KEY=...        # optional: translation into Tagalog, and a fallback (also set LLM_ENABLED=true)
```

Start it: `cd api && uvicorn app.main:app --port 8000`. Without `WHATSAPP_ENABLED=true` the webhook answers 404; without a `WORKER_HASH_SECRET` of at least 16 characters it
answers 503. With no Sarvam or Gemini key the bot still works: voice notes get "Voice isn't available right now, please type", and answers stay in English.

## 4. Give Twilio a public HTTPS URL

Twilio must reach your API from the internet. For a demo, a free Cloudflare quick tunnel works:

```
cloudflared tunnel --url http://localhost:8000
```

It prints an address like `https://something-random.trycloudflare.com`. Your webhook URL is that address plus `/whatsapp/webhook`. Put the **same string** in
`WHATSAPP_WEBHOOK_URL` and restart the API. (Twilio signs each request over the exact URL; if the two differ by a character, every message is refused with 403.)

## 5. Point the sandbox at it

Console → **Messaging → Try it out → Send a WhatsApp message → Sandbox settings**. In **When a message comes in** paste the webhook URL, method **POST**, and **Save**.
(Steve answers through Twilio's REST API, not in the webhook response, so the "status callback" box can stay empty.)

## 6. Test

1. From the phone that joined the sandbox, send `hello` to +1 415 523 8886. Steve replies with a numbered language picker.
2. Reply with a number (for example `2`). You get the language, one privacy line in that language, an example decode, and how to use it.
3. Send `yalla habibi come to the barking gate tree`. Expected reply (English shown):
   ```
   📍 Where: parking gate 3
   ✅ What: come
   💬 They said: "yalla habibi come to the barking gate tree"
   ℹ️ yalla = come on / let's go
   ℹ️ habibi = my dear / my beloved
   ```
4. **Forward a voice note** (long-press a voice note in any chat → Forward → the Steve sandbox contact), or record one directly in the Steve chat. Up to 30 seconds.
   You need `SARVAM_API_KEY` for this.
5. Try `come to the barking or the building?` and answer with `1`, `2` or `3`. Try `HELP`, `LANGUAGE`, `EN`.

## 7. If something does not work

| Symptom | Cause |
|---|---|
| No reply, Twilio logs show a `403` from your URL | the signature check failed: `WHATSAPP_WEBHOOK_URL` is not exactly the URL in Twilio (scheme, host, path, trailing slash), or `TWILIO_AUTH_TOKEN` is wrong |
| Twilio logs show `404` | `WHATSAPP_ENABLED` is not `true` |
| Twilio logs show `503` | `WORKER_HASH_SECRET` is missing or shorter than 16 characters |
| The webhook is fine but you get no reply | the reply could not be sent: check `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN`, that you joined the sandbox in the last three days, and the API log line `whatsapp reply not sent` (it names the error type, never the number or text) |
| Voice note: "I couldn't listen to that voice note" | the media could not be downloaded (Twilio asks for the Account SID and Auth Token when downloading; they are the ones in `.env`), or the speech service failed |
| You are answered once, then "You've sent a lot of messages" | the per-number limit (20 per hour, 100 per day) |
| Two answers to one message | Twilio redelivered it and the API restarted in between (duplicates are ignored only while the process runs) |

## 8. What Steve keeps, and what Twilio keeps

Steve stores **only** a keyed hash of the number, the language you chose and two anonymous counters (decodes and voice notes) in its database; audio is held in memory for one
speech-to-text call and dropped; message text is never stored or logged; an open question and the last English answer (for `EN`) stay in memory for 10 minutes.
**Twilio has its own copies**: it logs messages and keeps media it received according to its own retention settings. Steve does not delete anything on Twilio's side.
Twilio's documentation describes protecting media with HTTP basic authentication (Console → Messaging settings) and deleting media and messages through its API; use them
before showing this to real users. The privacy sentence in the onboarding ("I delete your voice notes after listening. Your boss can't see this chat.") is the owner's
wording: please check with a lawyer that it is accurate for your Twilio settings (see `copy_review.md`).

## 9. Limits of this set-up

The sandbox is not a production channel: it has a shared number, needs everyone to join, forgets them after three days, and cannot start a conversation with anyone.
A real deployment needs a WhatsApp Business number approved through Twilio or Meta, and (for anything Steve sends outside the 24-hour reply window) approved templates: Steve
never messages first, so it does not need them. The provider seam (`api/app/services/messaging/`) is where the Meta Cloud API would plug in.
