// The one-screen audio showcase (showcase branch): no nav, no other pages; record -> card -> question -> answer, translation, mic denied, voice off.
// 375 px, fake microphone, mock Sarvam. Run through `node e2e/run.mjs showcase`.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = "http://localhost:3000";
const MOCK = "http://127.0.0.1:9911";
const axeSrc = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "node_modules", "axe-core", "axe.min.js"), "utf8");
const results = [];
const ok = (name, cond, extra = "") => results.push([cond ? "PASS" : "FAIL", name, extra]);
const errors = [];
const setMock = (o) => fetch(`${MOCK}/__set`, { method: "POST", body: JSON.stringify(o) });

const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
async function open(opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 375, height: 740 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, permissions: ["microphone"], ...opts });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(`PAGEERR ${e.message.slice(0, 150)}`));
  p.on("console", (m) => { if (m.type() === "error") errors.push(`${p.url()} ${m.text().slice(0, 150)}`); });
  return { ctx, p };
}
const speak = async (p) => {
  await p.getByRole("button", { name: "Start recording" }).click();
  await p.waitForTimeout(1300);
  await p.getByRole("button", { name: "Stop recording" }).click();
};

await setMock({ transcript: "come to the barking or the building", translateMode: "prefix", sttFail: false });
const { ctx, p } = await open();
await p.goto(`${WEB}/`, { waitUntil: "networkidle" });
await p.getByRole("heading", { name: "Steve" }).waitFor();
ok("/ is the Steve screen, headed in Raleway", (await p.getByRole("heading", { name: "Steve" }).evaluate((el) => getComputedStyle(el).fontFamily)).toLowerCase().includes("raleway"));
ok("no top nav bar, no footer, no other links on the page", (await p.locator("header nav, nav, footer").count()) === 0 && (await p.locator("a[href]").count()) <= 1, `${await p.locator("a[href]").count()} links`);
ok("no language picker in the way: it starts in English", (await p.getByRole("heading", { name: "Choose your language" }).count()) === 0);
ok("nothing is decoded before the visitor speaks", (await p.getByTestId("decoded-card").count()) === 0);
ok("no Paste tab, no examples: audio only", (await p.getByRole("tab").count()) === 0 && (await p.getByTestId("examples").count()) === 0);
ok("no horizontal scroll at 375 px", await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
ok("no Next dev badge", (await p.locator("nextjs-portal, [data-nextjs-dev-tools-button]").count()) === 0);
const box = await p.locator('button[aria-label="Start recording"]').boundingBox();
ok("the record button is big (>= 44 px)", box.width >= 44 && box.height >= 44, `${Math.round(box.width)}x${Math.round(box.height)}`);
await p.evaluate(axeSrc);
const bad = (await p.evaluate(async () => (await window.axe.run(document, { resultTypes: ["violations"] })).violations.filter((v) => ["serious", "critical"].includes(v.impact)).map((v) => v.id)));
ok("axe: 0 serious/critical violations", bad.length === 0, bad.join(","));

await p.locator("#accent").selectOption("ar");
await p.getByRole("button", { name: "Start recording" }).click();
await p.getByTestId("other-person-notice").waitFor();
const notice = await p.getByTestId("other-person-notice").innerText();
ok("other-person notice in English and Arabic while recording", notice.includes("Steve is helping me understand") && notice.includes("ستيف يساعدني على الفهم"));
await p.waitForTimeout(1300);
await p.getByRole("button", { name: "Stop recording" }).click();
await p.getByTestId("questions").waitFor({ timeout: 20000 });
ok("the spoken audio is decoded and a question is asked, not a guess", (await p.getByTestId("questions").innerText()).includes("Parking or barking?") && (await p.getByTestId("action-where").count()) === 0);
ok("Say it back is shown as text", (await p.getByTestId("say-back").innerText()).includes("Sorry, parking or barking?"));
await p.getByTestId("questions").getByRole("button", { name: "parking", exact: true }).click();
await p.waitForFunction(() => !document.querySelector('[data-testid="questions"]'), null, { timeout: 15000 });
ok("answering resolves it in place: Where = parking", (await p.getByTestId("action-where").innerText()).includes("parking"));

await p.getByRole("button", { name: /Change language/ }).click();
await p.getByRole("button", { name: /മലയാളം/ }).click();
ok("choosing a language clears the old answer", (await p.getByTestId("decoded-card").count()) === 0);
await speak(p);
await p.getByTestId("decoded-card").waitFor({ timeout: 20000 });
ok("the card is also shown in the chosen language (translation first, English one tap away)", (await p.getByTestId("plain-english").innerText()).startsWith("[ml-IN]") && (await p.getByRole("button", { name: "Show English" }).count()) === 1);
await ctx.close();

const D = await open();
await D.ctx.addInitScript(() => { navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("Permission denied", "NotAllowedError")); });
await D.p.goto(`${WEB}/`, { waitUntil: "networkidle" });
await D.p.getByRole("button", { name: "Start recording" }).click();
await D.p.getByTestId("mic-problem").waitFor({ timeout: 10000 });
ok("mic denied: a clear message", /microphone is blocked/i.test(await D.p.getByTestId("mic-problem").innerText()));
await D.ctx.close();

const V = await open();
await V.p.route("**/decode/health", (route) => route.fulfill({ status: 200, headers: { "access-control-allow-origin": WEB, "content-type": "application/json" },
  body: JSON.stringify({ typed: true, voice: false, translation: { available: false }, languages: ["en"], accent_hints: ["ar"], budget: { stt_remaining: 0, stt_cap: 0 }, limits: { audio_seconds: 30, audio_bytes: 4194304, clarify_minutes: 10 } }) }));
await V.p.goto(`${WEB}/`, { waitUntil: "networkidle" });
await V.p.getByTestId("voice-off").waitFor();
ok("voice off: a message and no record button", (await V.p.getByRole("button", { name: "Start recording" }).count()) === 0);
await V.ctx.close();

await setMock({ sttFail: true });
const F = await open();
await F.p.goto(`${WEB}/`, { waitUntil: "networkidle" });
await speak(F.p);
await F.p.getByText(/couldn't listen to that voice note/i).waitFor({ timeout: 15000 });
ok("the speech service failing shows a friendly message", true);
await F.ctx.close();
await setMock({ sttFail: false });

for (const [s, n, e] of results) console.log(s, n, e);
console.log("browser errors:", errors.length ? "\n" + errors.join("\n") : "none");
const failed = results.some((r) => r[0] === "FAIL") || errors.some((e) => !/ERR_FAILED|status of 5/.test(e));
console.log(failed ? "SHOWCASE E2E FAILED" : "SHOWCASE E2E ALL PASSED");
await browser.close();
process.exitCode = failed ? 1 : 0;
