// /listen browser flows (Phase 6, D47): language picker, record -> card -> clarify -> resolved (fake microphone, mock Sarvam), paste flow, voice-unavailable
// fallback, language switch and RTL, no horizontal scroll at 360 px, touch targets, axe. Run through `node e2e/run.mjs listen`.
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
// D47: /listen is a minimal reference UI (the demo site is the teammate's), so accessibility and touch-target findings are reported, not gating.
const info = (name, cond, extra = "") => results.push([cond ? "PASS" : "INFO", name, extra]);
const errors = [];
const setMock = (o) => fetch(`${MOCK}/__set`, { method: "POST", body: JSON.stringify(o) });
const mockLog = async () => (await fetch(`${MOCK}/__log`)).json();

const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
async function open(opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 360, height: 740 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, permissions: ["microphone"], ...opts });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(`PAGEERR ${e.message.slice(0, 150)}`));
  p.on("console", (m) => { if (m.type() === "error") errors.push(`${p.url()} ${m.text().slice(0, 150)}`); });
  return { ctx, p };
}
const axe = async (p, label) => {
  await p.evaluate(axeSrc);
  const r = await p.evaluate(async () => (await window.axe.run(document, { resultTypes: ["violations"] })).violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, sel: v.nodes[0]?.target?.join(" ") })));
  const bad = r.filter((v) => v.impact === "serious" || v.impact === "critical");
  info(`axe: 0 serious/critical violations (${label})`, bad.length === 0, JSON.stringify(bad));
};
const big = async (p, loc, label, min = 56) => {
  const box = await p.locator(loc).first().boundingBox();
  info(`touch target >= ${min}px: ${label}`, !!box && box.height >= min - 0.5 && box.width >= min - 0.5, box ? `${Math.round(box.width)}x${Math.round(box.height)}` : "not found");
};
const noHScroll = async (p, label) => info(`no horizontal scroll at 360 px (${label})`, await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));

await setMock({ transcript: "come to the barking or the building", translateMode: "prefix", sttFail: false });

// ---- first run: language picker ------------------------------------------------------------------------------------------------------------
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

// ---- Listen: record -> card -> clarify -> resolved -------------------------------------------------------------------------------------------
await p.locator("#accent").selectOption("ar");
await big(p, 'button[aria-label="Start recording"]', "record button");
await big(p, '[role="tab"]:has-text("Listen")', "Listen tab");
await big(p, '[role="tab"]:has-text("Paste")', "Paste tab");
await big(p, "#accent", "accent select");
await noHScroll(p, "listen");
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
await p.getByTestId("decoded-card").waitFor({ timeout: 20000 });
ok("notice gone after recording", (await p.getByTestId("other-person-notice").count()) === 0);
const log = await mockLog();
const stt = log.find((c) => c.kind === "stt");
ok("the API asked Sarvam for transcribe / en-IN", stt?.mode === "transcribe" && stt?.lang === "en-IN", JSON.stringify(stt));
ok("card shows the translated sentence first", (await p.getByTestId("plain-english").innerText()).startsWith("[ml-IN]"));
ok("clarifying question and options are shown as buttons", (await p.getByTestId("questions").innerText()).includes("Parking or barking?") && (await p.getByRole("button", { name: "parking", exact: true }).count()) === 1);
ok("Where is not guessed while a question is open", (await p.getByTestId("action-where").count()) === 0);
ok("say it back phrase is large text", (await p.getByTestId("say-back").innerText()).includes("Sorry, parking or barking?"));
await big(p, '[data-testid="questions"] button:has-text("parking")', "option button");
await big(p, '[data-testid="questions"] button:has-text("Not sure")', "Not sure button");
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

// ---- Paste flow -------------------------------------------------------------------------------------------------------------------------------
await p.getByRole("tab", { name: /Paste/ }).click();
await p.locator("#accent").selectOption("hi");
await p.locator("#msg").fill("wery good, come at fife");
await big(p, 'button:has-text("Decode")', "Decode button");
await p.getByRole("button", { name: "Decode" }).click();
await p.getByTestId("decoded-card").waitFor();
await p.waitForFunction(() => document.querySelector('[data-testid="original"]')?.textContent?.includes("wery"));
await p.getByRole("button", { name: "Show English" }).click();
ok("paste: plain English", (await p.getByTestId("plain-english").innerText()).startsWith("Very good, come at 5"));
ok("paste: when is 5", (await p.getByTestId("action-when").innerText()).includes("5"));
await p.getByTestId("original").getByRole("button", { name: "wery" }).click();
ok("tapping a highlight shows its reason", /very/i.test(await p.getByTestId("highlight-detail").innerText()));
await axe(p, "paste result with a highlight");

// ---- voice trouble: the speech service fails -> Paste with the reason -----------------------------------------------------------------------
await setMock({ sttFail: true });
await p.getByRole("tab", { name: /Listen/ }).click();
await p.getByRole("button", { name: "Start recording" }).click();
await p.waitForTimeout(1200);
await p.getByRole("button", { name: "Stop recording" }).click();
await p.getByText(/couldn't listen to that voice note/i).waitFor({ timeout: 15000 });
ok("voice failure switches to Paste and says why", (await p.getByRole("tab", { name: /Paste/ }).getAttribute("aria-selected")) === "true");
await setMock({ sttFail: false });

// ---- language switch and right-to-left --------------------------------------------------------------------------------------------------------
await p.getByRole("button", { name: /Change language/ }).click();
await p.getByRole("heading", { name: "Choose your language" }).waitFor();
await p.getByRole("button", { name: /اردو/ }).click();
await p.getByRole("heading", { name: "Listen" }).waitFor();
ok("language switch is stored", (await p.evaluate(() => localStorage.getItem("steve_lang"))) === "ur");
await p.getByRole("tab", { name: /Paste/ }).click();
await p.locator("#msg").fill("don't come to the barking now, khalas");
await p.getByRole("button", { name: "Decode" }).click();
await p.getByTestId("decoded-card").waitFor();
await p.waitForFunction(() => document.querySelector('[data-testid="plain-english"]')?.textContent?.startsWith("[ur-IN]"));
ok("Urdu card is right-to-left", (await p.getByTestId("plain-english").getAttribute("dir")) === "rtl" && (await p.getByTestId("plain-english").getAttribute("lang")) === "ur");
await axe(p, "Urdu card");

// ---- English: no translation ---------------------------------------------------------------------------------------------------------------
await p.getByRole("button", { name: /Change language/ }).click();
await p.getByRole("button", { name: /^English/ }).click();
await p.getByRole("tab", { name: /Paste/ }).click();
await p.locator("#msg").fill("pay fifty dirhams tomorrow");
await p.getByRole("button", { name: "Decode" }).click();
await p.getByTestId("decoded-card").waitFor();
await p.waitForFunction(() => document.querySelector('[data-testid="plain-english"]')?.textContent?.startsWith("Pay 50 dirhams"));
ok("English: no translation toggle", (await p.getByRole("button", { name: /Show English|Show / }).count()) === 0 || (await p.getByRole("button", { name: "Show English" }).count()) === 0);
ok("how much is shown", (await p.getByTestId("action-how-much").innerText()).includes("50 dirhams"));
await ctx.close();

// ---- voice unavailable at load: starts on Paste with an explanation ----------------------------------------------------------------------------
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

// ---- an empty result ------------------------------------------------------------------------------------------------------------------------------
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

// ---- the API is unreachable: an error with retry ---------------------------------------------------------------------------------------------------
const X = await open();
await X.ctx.addInitScript(() => { localStorage.setItem("steve_lang", "en"); });
await X.p.goto(`${WEB}/listen`, { waitUntil: "networkidle" });
await X.p.route("**/decode", (route) => route.abort());
await X.p.getByRole("tab", { name: /Paste/ }).click();
await X.p.locator("#msg").fill("come at five");
await X.p.getByRole("button", { name: "Decode" }).click();
await X.p.getByRole("button", { name: "Try again" }).waitFor({ timeout: 15000 });
ok("error state with a retry button", (await X.p.getByRole("button", { name: "Try again" }).count()) >= 1, String(await X.p.getByRole("button", { name: "Try again" }).count()));
await X.p.unroute("**/decode");
await X.p.getByRole("button", { name: "Try again" }).click();
await X.p.getByTestId("decoded-card").waitFor({ timeout: 15000 });
ok("retry decodes the same message", (await X.p.getByTestId("plain-english").innerText()).includes("5"));
await X.ctx.close();

// ---- reduced motion and dark mode do not break the page ------------------------------------------------------------------------------------------
const R = await open({ reducedMotion: "reduce", colorScheme: "dark" });
await R.ctx.addInitScript(() => { localStorage.setItem("steve_lang", "en"); });
await R.p.goto(`${WEB}/listen`, { waitUntil: "networkidle" });
await R.p.getByRole("tab", { name: /Paste/ }).click();
await R.p.locator("#msg").fill("come to the barking or the building?");
await R.p.getByRole("button", { name: "Decode" }).click();
await R.p.getByTestId("questions").waitFor();
await axe(R.p, "dark mode, reduced motion, open question");
await R.ctx.close();

for (const [s, n, e] of results) console.log(s, n, e);
console.log("browser errors:", errors.length ? "\n" + errors.join("\n") : "none");
const failed = results.some((r) => r[0] === "FAIL");
console.log(`(${results.filter((r) => r[0] === "INFO").length} informational findings: accessibility and touch targets are not gating for the reference UI)`);
console.log(failed ? "LISTEN E2E FAILED" : "LISTEN E2E ALL PASSED");
await browser.close();
process.exitCode = failed ? 1 : 0;
