// The Decode demo in a browser (D50): entry page, language picker, example chips, record -> card -> clarify -> resolved (fake microphone, mock Sarvam), paste,
// voice trouble (service failure, over budget, mic denied), cold start ("Waking up the server"), language switch and RTL, the inspector, the Decode evaluation tab.
// Everything runs at 375 px: no horizontal scroll, tap targets >= 44 px, axe 0 serious/critical. Run through `node e2e/run.mjs demo`.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = "http://localhost:3000";
const MOCK = "http://127.0.0.1:9911";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const axeSrc = fs.readFileSync(path.join(HERE, "..", "node_modules", "axe-core", "axe.min.js"), "utf8");
const results = [];
const ok = (name, cond, extra = "") => results.push([cond ? "PASS" : "FAIL", name, extra]);
const errors = [];
const setMock = (o) => fetch(`${MOCK}/__set`, { method: "POST", body: JSON.stringify(o) });
const mockLog = async () => (await fetch(`${MOCK}/__log`)).json();

const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
async function open(opts = {}, b = browser) {
  const ctx = await b.newContext({ viewport: { width: 375, height: 740 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, permissions: ["microphone"], ...opts });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(`PAGEERR ${e.message.slice(0, 150)}`));
  p.on("console", (m) => { if (m.type() === "error" && !/ERR_FAILED|ERR_ABORTED|status of 5|status of 400/.test(m.text())) errors.push(`${p.url()} ${m.text().slice(0, 150)}`); });
  return { ctx, p };
}
const axe = async (p, label) => {
  await p.evaluate(axeSrc);
  const r = await p.evaluate(async () => (await window.axe.run(document, { resultTypes: ["violations"] })).violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, sel: v.nodes[0]?.target?.join(" ") })));
  const bad = r.filter((v) => v.impact === "serious" || v.impact === "critical");
  ok(`axe: 0 serious/critical violations (${label})`, bad.length === 0, JSON.stringify(bad));
};
const big = async (p, loc, label, min = 44) => {
  const box = await p.locator(loc).first().boundingBox();
  ok(`tap target >= ${min}px: ${label}`, !!box && box.height >= min - 0.5 && box.width >= min - 0.5, box ? `${Math.round(box.width)}x${Math.round(box.height)}` : "not found");
};
const noHScroll = async (p, label) => ok(`no horizontal scroll at 375 px (${label})`, await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
const noDevBadge = async (p, label) => ok(`no Next dev badge (${label})`, (await p.locator("nextjs-portal, [data-nextjs-dev-tools-button], [data-next-badge]").count()) === 0);

await setMock({ transcript: "come to the barking or the building", translateMode: "prefix", sttFail: false });

// ---- the entry page ---------------------------------------------------------------------------------------------------------------------------------------
const H = await open();
const healthCalls = [];
H.p.on("request", (r) => { if (r.url().endsWith("/decode/health")) healthCalls.push(r.url()); });
await H.p.goto(`${WEB}/`, { waitUntil: "networkidle" });
ok("/ shows the intro headline", (await H.p.getByRole("heading", { level: 1 }).innerText()).includes("You know the language. You still miss the message."));
ok("the first page load pings /decode/health (warm-up)", healthCalls.length >= 1);
await big(H.p, '[data-testid="try-it"]', "Try it button");
await H.p.getByTestId("live-example").waitFor({ timeout: 20000 });
const live = await H.p.getByTestId("live-example").innerText();
ok("the intro shows a LIVE decoded example (Al Quoz / Maghrib)", /al quoz/i.test(live) && /maghrib/i.test(live) && /Where/.test(live));
await H.p.getByRole("button", { name: "Open menu" }).click();
ok("the menu has Listen first and Check (teach-back) as a secondary link", (await H.p.getByRole("link", { name: "Listen" }).count()) >= 1 && (await H.p.getByRole("link", { name: "Check (teach-back)" }).count()) >= 1);
await H.p.getByRole("button", { name: "Close menu" }).click();
await noHScroll(H.p, "/");
await noDevBadge(H.p, "/");
await axe(H.p, "/ intro");
await H.p.getByTestId("try-it").click();
await H.p.waitForURL(/\/listen/);
ok("Try it opens /listen", true);
await H.ctx.close();

// ---- first run: language picker ------------------------------------------------------------------------------------------------------------------------------
const { ctx, p } = await open();
await p.goto(`${WEB}/listen`, { waitUntil: "networkidle" });
await p.getByRole("heading", { name: "Choose your language" }).waitFor({ timeout: 15000 });
const pickerText = await p.locator("body").innerText();
ok("first-run picker shows language names in their own scripts", ["മലയാളം", "हिंदी", "اردو", "Tagalog", "বাংলা", "English"].every((n) => pickerText.includes(n)));
await noHScroll(p, "picker");
await big(p, 'button[lang="ml"]', "language button");
await axe(p, "language picker");
await p.getByRole("button", { name: /മലയാളം/ }).click();
await p.getByRole("heading", { name: "Listen" }).waitFor();
ok("the chosen language is stored on this phone", (await p.evaluate(() => localStorage.getItem("steve_lang"))) === "ml");
ok("nothing but keys and choices is stored", (await p.evaluate(() => Object.keys(localStorage).sort().join(","))).split(",").every((k) => ["steve_lang", "steve_worker_key", "steve_accent"].includes(k)));

// ---- example chips: decoded live through the real API ------------------------------------------------------------------------------------------------------------
await p.getByTestId("examples").getByRole("button").first().waitFor({ timeout: 20000 });
const chips = await p.getByTestId("examples").getByRole("button").allInnerTexts();
ok("example chips come from GET /decode/examples (six, including Al Quoz / Maghrib)", chips.length >= 5 && chips.some((c) => /Al Quoz/i.test(c)), chips.join(" | "));
await big(p, '[data-testid="examples"] button', "example chip");
await p.getByTestId("examples").getByRole("button", { name: /Al Quoz/i }).click();
await p.getByTestId("decoded-card").waitFor({ timeout: 20000 });
await p.getByRole("button", { name: "Show English" }).click();
ok("Al Quoz example: where / when / what from the live engine", /al quoz/i.test(await p.getByTestId("action-where").innerText()) && /maghrib/i.test(await p.getByTestId("action-when").innerText()) && /drop/i.test(await p.getByTestId("action-what").innerText()));
ok("the example filled the Paste box", (await p.locator("#msg").inputValue()).startsWith("Yalla, drop it at Al Quoz"));
await p.getByTestId("examples").getByRole("button", { name: /question, not a guess/i }).click();
await p.getByTestId("questions").waitFor({ timeout: 20000 });
ok("no stray characters rendered in the card (a bare 0 once leaked from a numeric condition)", !(await p.getByTestId("decoded-card").innerText()).split("
").some((l) => l.trim() === "0"));
ok("the question example asks instead of guessing", (await p.getByTestId("questions").innerText()).includes("Parking or barking?"));
await p.getByTestId("questions").getByRole("button", { name: "parking", exact: true }).click();
await p.waitForFunction(() => !document.querySelector('[data-testid="questions"]'), null, { timeout: 15000 });
ok("clarify from an example chip resolves in place", /parking/i.test(await p.getByTestId("action-where").innerText()));

// ---- Listen: record -> card -> clarify -> resolved -------------------------------------------------------------------------------------------------------------------
await p.getByRole("tab", { name: /Listen/ }).click();
await p.locator("#accent").selectOption("ar");
await big(p, 'button[aria-label="Start recording"]', "record button");
await big(p, '[role="tab"]:has-text("Listen")', "Listen tab");
await big(p, '[role="tab"]:has-text("Paste")', "Paste tab");
await big(p, "#accent", "accent select");
await big(p, 'button[aria-label*="Change language"]', "language button");
await noHScroll(p, "listen");
await noDevBadge(p, "/listen");
await axe(p, "listen tab");
ok("no notice before recording", (await p.getByTestId("other-person-notice").count()) === 0);
await p.getByRole("button", { name: "Start recording" }).click();
await p.getByTestId("other-person-notice").waitFor();
const notice = await p.getByTestId("other-person-notice").innerText();
ok("other-person notice in English and Arabic while recording", notice.includes("Steve is helping me understand. Nothing is recorded.") && notice.includes("ستيف يساعدني على الفهم"));
ok("the Arabic line is right-to-left", (await p.locator('[data-testid="other-person-notice"] [lang="ar"]').getAttribute("dir")) === "rtl");
await axe(p, "recording notice");
await p.waitForTimeout(1500);
await p.getByRole("button", { name: "Stop recording" }).click();
await p.getByTestId("questions").waitFor({ timeout: 20000 });
ok("notice gone after recording", (await p.getByTestId("other-person-notice").count()) === 0);
const stt = (await mockLog()).find((c) => c.kind === "stt");
ok("the API asked Sarvam for transcribe / en-IN", stt?.mode === "transcribe" && stt?.lang === "en-IN", JSON.stringify(stt));
ok("card shows the translated sentence first", (await p.getByTestId("plain-english").innerText()).startsWith("[ml-IN]"));
ok("clarifying question and options are shown as buttons", (await p.getByTestId("questions").innerText()).includes("Parking or barking?") && (await p.getByRole("button", { name: "parking", exact: true }).count()) === 1);
ok("Where is not guessed while a question is open", (await p.getByTestId("action-where").count()) === 0);
ok("say it back phrase is large text", (await p.getByTestId("say-back").innerText()).includes("Sorry, parking or barking?"));
await big(p, '[data-testid="questions"] button:has-text("parking")', "option button");
await big(p, '[data-testid="questions"] button:has-text("Not sure")', "Not sure button");
await big(p, 'button:has-text("Show English")', "Show English toggle");
await noHScroll(p, "card with question");
await axe(p, "card with an open question");
await p.getByRole("button", { name: "Show English" }).click();
ok("toggle shows the English card", !(await p.getByTestId("plain-english").innerText()).startsWith("[ml-IN]"));
await p.getByRole("button", { name: "parking", exact: true }).click();
await p.waitForFunction(() => !document.querySelector('[data-testid="questions"]'), null, { timeout: 15000 });
ok("answering resolves the question in place", (await p.getByTestId("questions").count()) === 0);
ok("the device key is created on first use and kept on this phone", /^wk_[A-Za-z0-9_-]{24,}$/.test((await p.evaluate(() => localStorage.getItem("steve_worker_key"))) || "wk_"));
ok("Where is now filled in", (await p.getByTestId("action-where").innerText()).includes("parking"));
ok("say it back changes once nothing is open", !(await p.getByTestId("say-back").innerText()).includes("Sorry, parking"));
await axe(p, "resolved card");

// ---- Paste flow ---------------------------------------------------------------------------------------------------------------------------------------------------
await p.getByRole("tab", { name: /Paste/ }).click();
await p.locator("#accent").selectOption("hi");
await p.locator("#msg").fill("wery good, come at fife");
await big(p, 'button:has-text("Decode")', "Decode button");
await p.getByRole("button", { name: "Decode" }).click();
await p.waitForFunction(() => document.querySelector('[data-testid="original"]')?.textContent?.includes("wery"), null, { timeout: 20000 });
await p.getByRole("button", { name: "Show English" }).click();
ok("paste: plain English", (await p.getByTestId("plain-english").innerText()).startsWith("Very good, come at 5"));
ok("paste: when is 5", (await p.getByTestId("action-when").innerText()).includes("5"));
await p.getByTestId("original").getByRole("button", { name: "wery" }).click();
ok("tapping a highlight shows its reason", /very/i.test(await p.getByTestId("highlight-detail").innerText()));
await axe(p, "paste result with a highlight");

// ---- voice trouble: the speech service fails -> Paste with the reason ------------------------------------------------------------------------------------------
await setMock({ sttFail: true });
await p.getByRole("tab", { name: /Listen/ }).click();
await p.getByRole("button", { name: "Start recording" }).click();
await p.waitForTimeout(1200);
await p.getByRole("button", { name: "Stop recording" }).click();
await p.getByText(/couldn't listen to that voice note/i).waitFor({ timeout: 15000 });
ok("voice failure switches to Paste and says why", (await p.getByRole("tab", { name: /Paste/ }).getAttribute("aria-selected")) === "true");
await setMock({ sttFail: false });

// ---- voice over budget (simulated answer from the API) -> Paste with the message ------------------------------------------------------------------------------
await p.route("**/decode", async (route) => {
  if (route.request().method() === "POST" && (route.request().headers()["content-type"] || "").includes("multipart"))
    return route.fulfill({ status: 200, headers: { "access-control-allow-origin": WEB, "content-type": "application/json" }, body: JSON.stringify({ card: null, translation: null, transcript: null, decode_id: null, notes: ["Voice is busy for today, please type or paste the message."], say_back: [] }) });
  return route.continue();
});
await p.getByRole("tab", { name: /Listen/ }).click();
await p.getByRole("button", { name: "Start recording" }).click();
await p.waitForTimeout(1200);
await p.getByRole("button", { name: "Stop recording" }).click();
await p.getByText(/Voice is busy for today/i).waitFor({ timeout: 15000 });
ok("voice over budget: Paste tab with the message", (await p.getByRole("tab", { name: /Paste/ }).getAttribute("aria-selected")) === "true");
await p.unroute("**/decode");

// ---- language switch and right-to-left --------------------------------------------------------------------------------------------------------------------------------
await p.getByRole("button", { name: /Change language/ }).click();
await p.getByRole("heading", { name: "Choose your language" }).waitFor();
await p.getByRole("button", { name: /اردو/ }).click();
await p.getByRole("heading", { name: "Listen" }).waitFor();
ok("language switch is stored", (await p.evaluate(() => localStorage.getItem("steve_lang"))) === "ur");
await p.getByRole("tab", { name: /Paste/ }).click();
await p.locator("#msg").fill("don't come to the barking now, khalas");
await p.getByRole("button", { name: "Decode" }).click();
await p.waitForFunction(() => document.querySelector('[data-testid="plain-english"]')?.textContent?.startsWith("[ur-IN]"), null, { timeout: 20000 });
ok("Urdu card is right-to-left", (await p.getByTestId("plain-english").getAttribute("dir")) === "rtl" && (await p.getByTestId("plain-english").getAttribute("lang")) === "ur");
await axe(p, "Urdu card");

// ---- English: no translation ---------------------------------------------------------------------------------------------------------------------------------------------
await p.getByRole("button", { name: /Change language/ }).click();
await p.getByRole("button", { name: /^English/ }).click();
await p.getByRole("tab", { name: /Paste/ }).click();
await p.locator("#msg").fill("pay fifty dirhams tomorrow");
await p.getByRole("button", { name: "Decode" }).click();
await p.waitForFunction(() => document.querySelector('[data-testid="plain-english"]')?.textContent?.startsWith("Pay 50 dirhams"), null, { timeout: 20000 });
ok("English: no translation toggle", (await p.getByRole("button", { name: "Show English" }).count()) === 0);
ok("how much is shown", (await p.getByTestId("action-how-much").innerText()).includes("50 dirhams"));
await ctx.close();

// ---- cold start: the API does not answer at first ------------------------------------------------------------------------------------------------------------------------------
const C = await open();
await C.ctx.addInitScript(() => { localStorage.setItem("steve_lang", "en"); });
let refused = 0;
await C.p.route("**/decode/health", (route) => (refused++ < 2 ? route.abort() : route.continue()));
await C.p.route("**/decode/examples", (route) => (refused++ < 4 ? route.abort() : route.continue()));
await C.p.goto(`${WEB}/listen`, { waitUntil: "domcontentloaded" });
await C.p.getByTestId("waking").waitFor({ timeout: 15000 });
ok("cold start: 'Waking up the server' is shown", /Waking up the server/.test(await C.p.getByTestId("waking").innerText()));
await C.p.getByTestId("examples").getByRole("button").first().waitFor({ timeout: 40000 });
ok("cold start: the app retries and recovers by itself", true);
let posts = 0;
await C.p.route("**/decode", (route) => (route.request().method() === "POST" && posts++ < 1 ? route.abort() : route.continue()));
await C.p.getByRole("tab", { name: /Paste/ }).click();
await C.p.locator("#msg").fill("come at five");
await C.p.getByRole("button", { name: "Decode" }).click();
await C.p.getByTestId("decoded-card").waitFor({ timeout: 40000 });
ok("a decode that could not connect is retried and answered", (await C.p.getByTestId("plain-english").innerText()).includes("5") && posts >= 2);
await C.ctx.close();

// ---- microphone permission denied -> Paste with a clear message ------------------------------------------------------------------------------------------------------------------------
// Chromium's --deny-permission-prompts answers NotSupportedError in this environment, not the NotAllowedError a real browser gives when the user taps Block,
// so the refusal is reproduced exactly: getUserMedia rejects with a DOMException named NotAllowedError.
const D = await open();
await D.ctx.addInitScript(() => {
  localStorage.setItem("steve_lang", "en");
  navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
});
await D.p.goto(`${WEB}/listen`, { waitUntil: "networkidle" });
await D.p.getByRole("button", { name: "Start recording" }).click();
await D.p.getByTestId("mic-problem").first().waitFor({ timeout: 10000 });
ok("mic denied: a clear message is shown", /microphone is blocked/i.test(await D.p.getByTestId("mic-problem").first().innerText()), await D.p.getByTestId("mic-problem").first().innerText());
ok("mic denied: the Paste tab is selected so the demo can continue", (await D.p.getByRole("tab", { name: /Paste/ }).getAttribute("aria-selected")) === "true");
await D.p.locator("#msg").fill("come at five");
await D.p.getByRole("button", { name: "Decode" }).click();
await D.p.getByTestId("decoded-card").waitFor({ timeout: 20000 });
ok("mic denied: pasting still works", true);
await D.ctx.close();

// ---- voice off at load; empty result; API error and retry -------------------------------------------------------------------------------------------------------------------------------
const V = await open();
await V.ctx.addInitScript(() => { localStorage.setItem("steve_lang", "en"); });
await V.p.route("**/decode/health", (route) => route.fulfill({ status: 200, headers: { "access-control-allow-origin": WEB, "content-type": "application/json" },
  body: JSON.stringify({ typed: true, voice: false, translation: { available: false }, languages: ["en"], accent_hints: ["ar"], budget: { stt_remaining: 0, stt_cap: 0 }, limits: { audio_seconds: 30, audio_bytes: 4194304, clarify_minutes: 10 } }) }));
await V.p.goto(`${WEB}/listen`, { waitUntil: "networkidle" });
await V.p.getByRole("tab", { name: /Paste/ }).waitFor();
ok("voice off: Paste tab is selected on arrival", (await V.p.getByRole("tab", { name: /Paste/ }).getAttribute("aria-selected")) === "true");
await V.p.getByRole("tab", { name: /Listen/ }).click();
await V.p.getByTestId("voice-off").waitFor();
ok("voice off: the Listen tab explains it and has no record button", (await V.p.getByRole("button", { name: "Start recording" }).count()) === 0);
await V.ctx.close();

await setMock({ transcript: "" });
const E = await open();
await E.ctx.addInitScript(() => { localStorage.setItem("steve_lang", "en"); });
await E.p.goto(`${WEB}/listen`, { waitUntil: "networkidle" });
await E.p.getByRole("button", { name: "Start recording" }).click();
await E.p.waitForTimeout(1200);
await E.p.getByRole("button", { name: "Stop recording" }).click();
await E.p.getByText("I couldn't find anything to decode. Try again or paste the message.").first().waitFor({ timeout: 15000 });
ok("empty result: friendly message", true);
await E.ctx.close();

const X = await open();
await X.ctx.addInitScript(() => { localStorage.setItem("steve_lang", "en"); });
await X.p.goto(`${WEB}/listen`, { waitUntil: "networkidle" });
await X.p.route("**/decode", (route) => (route.request().method() === "POST" ? route.fulfill({ status: 400, headers: { "access-control-allow-origin": WEB, "content-type": "application/json" }, body: JSON.stringify({ detail: "Something is off with that message." }) }) : route.continue()));
await X.p.getByRole("tab", { name: /Paste/ }).click();
await X.p.locator("#msg").fill("come at five");
await X.p.getByRole("button", { name: "Decode" }).click();
await X.p.getByRole("button", { name: "Try again" }).waitFor({ timeout: 15000 });
ok("API error: an error with a retry button", (await X.p.getByRole("button", { name: "Try again" }).count()) >= 1);
await X.p.unroute("**/decode");
await X.p.getByRole("button", { name: "Try again" }).click();
await X.p.getByTestId("decoded-card").waitFor({ timeout: 15000 });
ok("retry decodes the same message", (await X.p.getByTestId("plain-english").innerText()).includes("5"));
await X.ctx.close();

// ---- how it works (the inspector) --------------------------------------------------------------------------------------------------------------------------------------------------------------------
const I = await open();
await I.p.goto(`${WEB}/how-it-works`, { waitUntil: "networkidle" });
await I.p.getByTestId("inspector-stages").waitFor({ timeout: 30000 });
ok("inspector shows all six stages", (await I.p.locator('[data-testid="inspector-stages"] section').count()) === 6);
const barking = await I.p.getByTestId("examined-barking").innerText();
ok("inspector: barking is rewritten to parking with scores", /rewritten: parking/.test(barking) && /as written/.test(barking));
ok("inspector: the local phrases are found first", /yalla/.test(await I.p.getByTestId("inspector-stages").innerText()));
ok("inspector: plain English at stage 5", (await I.p.getByTestId("inspector-plain").innerText()).includes("parking gate 3"));
await I.p.locator("#ins-text").fill("come to the barking or the building?");
await I.p.getByRole("button", { name: "Show the stages" }).click();
await I.p.waitForFunction(() => document.querySelector('[data-testid="inspector-stages"]')?.textContent?.includes("Question instead of a guess"), null, { timeout: 15000 });
ok("inspector: an open question is shown, not a guess", true);
ok("inspector says no language model is used", /No language model is used/.test(await I.p.locator("main").innerText()));
await noHScroll(I.p, "how it works");
await axe(I.p, "how it works");
await I.p.getByRole("tab", { name: "Check mode" }).click();
await I.p.getByText(/Zero LLMs in the verdict/).waitFor({ timeout: 10000 });
ok("how it works: the Check-mode inspector is still there", true);
await I.ctx.close();

// ---- the Decode evaluation tab ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
const V2 = await open();
await V2.p.goto(`${WEB}/eval`, { waitUntil: "networkidle" });
await V2.p.getByTestId("eval-voice_net").waitFor({ timeout: 30000 });
const evText = await V2.p.locator("main").innerText();
ok("eval: 'Read this first' with the no-real-workers caveat", /Read this first/.test(evText) && /synthetic/i.test(evText));
ok("eval: every section shows a label", (await V2.p.getByTestId("eval-label").count()) >= 6);
const vn = await V2.p.getByTestId("eval-voice_net").innerText();
ok("eval: the voice-net catch rate carries 'tuned on it' and the held-out 0/72", /tuned on it/.test(vn) && /0\.0% \(0\/72\)/.test(vn));
ok("eval: the false-alarm, typed-ear and extraction headlines are there", (await V2.p.getByTestId("eval-false_alarm").count()) === 1 && (await V2.p.getByTestId("eval-typed_ear").count()) === 1 && (await V2.p.getByTestId("eval-extraction").count()) === 1);
ok("eval: the Gemini baseline is shown", /Gemini/.test(await V2.p.getByTestId("eval-baseline").innerText()));
ok("eval: 'what has not been measured' is there", (await V2.p.getByTestId("eval-missing").count()) === 1);
await noHScroll(V2.p, "evaluation");
await axe(V2.p, "evaluation");
await V2.p.getByRole("tab", { name: "Check mode" }).click();
await V2.p.getByText(/false “understood”/).first().waitFor({ timeout: 20000 });
ok("eval: the Check-mode evaluation is still there", true);
await V2.ctx.close();

// ---- Check mode is reachable as a secondary from the nav ------------------------------------------------------------------------------------------------------------------------------------------------
const K = await open({ viewport: { width: 1200, height: 800 }, isMobile: false });
await K.p.goto(`${WEB}/`, { waitUntil: "networkidle" });
await K.p.getByRole("link", { name: "Check (teach-back)" }).first().click();
await K.p.waitForURL(/\/check/);
ok("Check mode landing is at /check and still works", (await K.p.locator("body").innerText()).includes("understanding"));
await K.ctx.close();

for (const [s, n, e] of results) console.log(s, n, e);
console.log("browser errors:", errors.length ? "\n" + errors.join("\n") : "none");
const failed = results.some((r) => r[0] === "FAIL") || errors.length > 0;
console.log(failed ? "DEMO E2E FAILED" : "DEMO E2E ALL PASSED");
await browser.close();
process.exitCode = failed ? 1 : 0;
