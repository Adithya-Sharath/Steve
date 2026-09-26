# Deploying Steve: Render (API) + Vercel (web)

The demo is two services: **the API on Render** (Docker, free plan) and **the web app on Vercel**. You create the accounts and click; nothing in this repo contains a secret.
Order matters because each side needs the other's URL: **1. Render → 2. Vercel → 3. back to Render**. Budget: about 30 minutes, most of it waiting for the first Docker build.

> **Honest notes before you start**
> * The API's Docker image has **never been built on our machines** (Docker Desktop was off). The first Render build is the first real build. If it fails, copy the build log to me.
> * Render's **free plan sleeps** after about 15 minutes idle and needs up to a minute to wake. The web app handles it: it pings the API on the first page load and shows "Waking up the server…" while it retries (for up to 60 s). For a live demo, open the site a minute before you present.
> * Render's free **disk is ephemeral**. Decode (paste, listen, examples, translation, the inspector, the evaluation numbers) keeps nothing on disk and does not care. Check mode's database (SQLite) and the WhatsApp preferences start **empty after every restart or deploy**; the tables are created on boot.
> * **Keys are optional.** With no Sarvam and no Gemini key the whole demo works in Paste mode with English cards. Voice notes and translation switch on when you add `SARVAM_API_KEY` (and Tagalog/fallback translation with `GEMINI_API_KEY`).
> * Never paste a key into a chat, an issue or a file in the repo. If you did already, rotate it in the provider's dashboard.

## 0. What has to be true first

* The code is on GitHub `Adithya-Sharath/Steve`, **branch `main`**, and contains `render.yaml` (repo root) and `web/vercel.json`. (I merge `decode` into `main` and tag `v2.0.0` only after the final audit is green; tell me if you see no `render.yaml` on `main`.)
* You have a **Render** account and a **Vercel** account, both signed in with GitHub, and both allowed to see the `Steve` repository (GitHub → Settings → Applications → configure each app's repository access).

## 1. Render: the API

1. Render dashboard → **New +** → **Blueprint**.
2. **Connect** the `Adithya-Sharath/Steve` repository (authorise Render on GitHub if asked), branch **`main`**. Render finds `render.yaml` and shows one service, **steve-api** (Docker, plan Free, region Oregon).
3. Render asks for the values marked `sync: false`. Enter:
   | Variable | Enter now |
   |---|---|
   | `PUBLIC_WEB_URL` | `https://placeholder.invalid` (you fix it in step 3) |
   | `CORS_ORIGINS` | `http://localhost:3000` (you fix it in step 3) |
   | `SARVAM_API_KEY` | your Sarvam key, or leave empty (voice notes and Indic translation stay off) |
   | `GEMINI_API_KEY` | your Gemini key, or leave empty (Tagalog and fallback translation stay off) |
4. Click **Apply** / **Create**. Render builds the Docker image (5 to 10 minutes) and starts it. Watch **Events / Logs** until it says *Live*.
5. Copy the service URL at the top of the page: `https://steve-api-XXXX.onrender.com` (this is your **API URL**).
6. Check it in a browser: `API_URL/health` should show `{"status":"ok", ...}` and `API_URL/decode/examples` should show six examples. **If either fails, stop and send me the log.**

## 2. Vercel: the web app

1. Vercel dashboard → **Add New…** → **Project** → import `Adithya-Sharath/Steve`.
2. **Root Directory: click Edit and choose `web`.** Framework Preset: **Next.js** (auto-detected). Leave build and output settings as they are (`web/vercel.json` only adds security headers).
3. **Environment Variables** (before you click Deploy): `NEXT_PUBLIC_API_URL` = your **API URL** from step 1.5 (`https://steve-api-XXXX.onrender.com`, **no trailing slash**). It is baked in at build time, so if it is ever wrong you must **redeploy** after fixing it.
4. **Deploy.** When it finishes, copy the production URL: `https://<project>.vercel.app` (this is your **web URL**; it is what your teammates link to, e.g. `WEB_URL/listen`).

## 3. Render again: tell the API who may call it

Render → **steve-api** → **Environment** → edit:

| Variable | Set to |
|---|---|
| `PUBLIC_WEB_URL` | your **web URL** (`https://<project>.vercel.app`, no trailing slash) |
| `CORS_ORIGINS` | your web URL, your teammates' landing-page domain, and localhost, comma-separated, no spaces, no trailing slashes: `https://<project>.vercel.app,https://TEAMMATES-DOMAIN,http://localhost:3000`. Add every origin that will call the API from a browser (the teammates' page only needs it if it calls the API itself; a plain link to `WEB_URL/listen` needs nothing). |

Save. Render redeploys (about a minute).

## 4. Check it works

Open `WEB_URL` on your phone:
1. The intro shows a live example (Al Quoz / Maghrib). If it stays blank for more than a minute, the API URL in Vercel is wrong or `CORS_ORIGINS` does not list the web URL.
2. **Try it** → pick a language → tap an example chip → a card appears; tap the question example and answer it.
3. Paste `wery good, come at fife` and Decode.
4. If you set `SARVAM_API_KEY`: tap the big button, speak, tap again (the microphone needs the HTTPS site, which Vercel provides).
5. `WEB_URL/how-it-works` and `WEB_URL/eval` show the stages and the labelled numbers.

## 5. Send me the two URLs

When it works (or when something does not), send me **the web URL and the API URL**. I then run the production smoke test with Playwright (paste example → card → clarify → translation, the health endpoint, the security headers, a 429 from the rate limit, the microphone permission prompt over HTTPS) and record the results in `docs/FINAL_AUDIT.md`. The smoke test spends only a few calls from the Sarvam and Gemini budgets.

## Environment variables

**Render (`steve-api`)**: all of these are in `render.yaml`; the ones that need you are marked.

| Variable | Value | Notes |
|---|---|---|
| `PUBLIC_WEB_URL` | web URL | **you set** (step 3) |
| `CORS_ORIGINS` | comma-separated origins | **you set** (step 3) |
| `TRUST_PROXY` | `true` | already set; needed so rate limits count each visitor, not Render's proxy |
| `ADMIN_KEY` | random | Render generates it. Open `WEB_URL/admin` and paste it once to get the LLM switch (optional) |
| `WORKER_HASH_SECRET` | random | Render generates it; only used if you switch WhatsApp on; never change it afterwards |
| `SARVAM_API_KEY` | your key | optional; **you set** (empty = voice and Indic translation off) |
| `GEMINI_API_KEY` | your key | optional; **you set** (empty = Tagalog/fallback translation off) |
| `LLM_ENABLED` | `false` | set `true` only with a Gemini key |
| `STT_DAILY_CAP`, `TRANSLATE_DAILY_CAP`, `LLM_DAILY_CAP` | `100` each | daily caps (all users together), **keep them on**; also set spending limits in the Sarvam and Google consoles |
| `WHATSAPP_ENABLED` | `false` | see `docs/whatsapp-setup.md` before changing |
| `PORT` | set by Render | the container binds `${PORT:-8000}` |

Everything else in `.env.example` has a safe default (rate limits, audio caps, the 10-minute question memory).

**Vercel (`web`)**

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | the API URL, no trailing slash (build time) |

## Later

* **A custom domain:** add it in Vercel (Domains) and put the new origin into `CORS_ORIGINS` on Render.
* **Updating:** push to `main`; Render and Vercel redeploy by themselves.
* **Rotating a key:** change it in the provider's dashboard, then in Render's Environment tab.
* **Not free forever / not for real users:** the free plans are for a demo. Real users need a paid Render instance (no sleeping), a database that survives restarts if you want Check mode's history, provider-side spending limits, and the reviews listed in the README (native speakers, a lawyer for in-person listening).
