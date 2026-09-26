// Retake the Decode screenshots from the PRODUCTION build at 375 px (D50): `node e2e/run.mjs shots`. Uses the mock Sarvam and the real engine.
import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = "http://localhost:3000";
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "screenshots");
const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
const open = async (opts = {}) => {
  const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, permissions: ["microphone"], ...opts });
  await ctx.addInitScript(() => localStorage.setItem("steve_lang", "ml"));
  return { ctx, p: await ctx.newPage() };
};
const shot = (p, name, full = false) => p.screenshot({ path: path.join(OUT, name), fullPage: full });

let { ctx, p } = await open();
await p.goto(`${WEB}/`, { waitUntil: "networkidle" });
await p.getByTestId("live-example").waitFor({ timeout: 20000 });
await shot(p, "decode-home.png", true);
await p.goto(`${WEB}/listen`, { waitUntil: "networkidle" });
await p.getByTestId("examples").getByRole("button").first().waitFor({ timeout: 20000 });
await shot(p, "decode-listen.png");
await p.getByTestId("examples").getByRole("button", { name: /question, not a guess/i }).click();
await p.getByTestId("questions").waitFor({ timeout: 20000 });
await shot(p, "decode-question.png", true);
await p.getByRole("button", { name: "Show English" }).click();
await p.getByTestId("questions").getByRole("button", { name: "parking", exact: true }).click();
await p.waitForFunction(() => !document.querySelector('[data-testid="questions"]'), null, { timeout: 15000 });
await shot(p, "decode-card.png", true);
await ctx.close();

({ ctx, p } = await open());
await p.goto(`${WEB}/how-it-works`, { waitUntil: "networkidle" });
await p.getByTestId("inspector-stages").waitFor({ timeout: 30000 });
await shot(p, "decode-inspector.png", true);
await p.goto(`${WEB}/eval`, { waitUntil: "networkidle" });
await p.getByTestId("eval-voice_net").waitFor({ timeout: 30000 });
await shot(p, "decode-eval.png", true);
await ctx.close();
await browser.close();
console.log("screenshots written to docs/screenshots");
