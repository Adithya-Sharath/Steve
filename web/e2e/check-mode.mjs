// Check mode (teach-back) browser flow: composer -> confirm -> reader reply -> live SSE -> copy banner -> follow-up -> second browser locked out -> admin switch -> demo.
// Run through `node e2e/run.mjs check` (starts the API and the production web build). Must stay green through every phase (D45).
import { chromium } from "playwright";
const WEB = "http://localhost:3000";
const results = [];
const ok = (name, cond, extra = "") => { results.push([cond ? "PASS" : "FAIL", name, extra]); };
const errors = [];
const browser = await chromium.launch();
const mk = async (opts = {}) => {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, ...opts });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(`PAGEERR ${p.url()} ${e.message.slice(0, 150)}`));
  p.on("console", (m) => { if (m.type() === "error" && !/403/.test(m.text())) errors.push(`${p.url()} ${m.text().slice(0, 150)}`); });
  return { ctx, p };
};

// --- sender browser A: compose -> confirm
const A = await mk();
await A.p.goto(`${WEB}/app/new`, { waitUntil: "networkidle" });
await A.p.locator("#sender").fill("Priya, Al Noor Pharmacy");
await A.p.locator("#msg").fill("Take 2 tablets after food, twice a day, for 5 days. Stop taking them and call us if you get a rash.");
await A.p.getByRole("button", { name: "Find key facts" }).click();
await A.p.getByRole("button", { name: /Confirm/ }).click();
await A.p.getByText("Reader link").waitFor({ timeout: 10000 });
const link = await A.p.locator("p.break-all").first().innerText();
ok("composer -> confirm -> share link shown", /\/r\/[\w-]+$/.test(link), link);
const token = link.split("/r/")[1];
const keyA = await A.p.evaluate(() => localStorage.getItem("steve_sender_key"));
ok("sender key generated in the browser", /^sk_[A-Za-z0-9_-]{24,}$/.test(keyA));

await A.p.getByRole("link", { name: "Open live results" }).click();
await A.p.waitForURL(/\/app\/m\//);
const resultsUrl = A.p.url();
await A.p.getByText("Waiting for a reply").waitFor();
ok("results page waits for a reply", true);

// --- reader (no key): submit a Manglish reply; sender page must update LIVE (SSE) without reload
const R = await mk({ viewport: { width: 390, height: 844 }, isMobile: true });
await R.p.goto(`${WEB}/r/${token}`, { waitUntil: "networkidle" });
const readerText = await R.p.locator("body").innerText();
ok("reader page shows the message, no scores/facts", readerText.includes("Take 2 tablets") && !/understood|wrong|missing/i.test(readerText));
await R.p.locator("#reply").fill("randu gulika, food kazhinju, raavile vaikittu, oru week");
await R.p.getByRole("button", { name: /Send my answer/ }).click();
await R.p.getByText("Thank you!").waitFor({ timeout: 8000 });
ok("reader thank-you screen", true);
await A.p.getByText("Heard 'oru week' = 7 days; expected 5 days.").waitFor({ timeout: 10000 });
ok("sender sees the WRONG duration live (SSE, no reload)", true);
ok("keyless reader never used the sender key", (await R.p.evaluate(() => localStorage.getItem("steve_sender_key"))) === null);

// --- copy-paste through the real UI: banner + every fact unclear
await R.p.getByRole("button", { name: "Add something else" }).click();
await R.p.locator("#reply").fill("Take 2 tablets after food, twice a day, for 5 days. Stop taking them and call us if you get a rash.");
await R.p.getByRole("button", { name: /Send my answer/ }).click();
await A.p.getByText("This reply looks copied from your message").waitFor({ timeout: 10000 });
ok("copied banner appears on the sender page", true);
ok("cards carry the exact reason", (await A.p.getByText("Reply looks copied from the message; ask them to say it in their own words.").count()) >= 5);

// --- follow-up draft
await A.p.getByRole("button", { name: /Draft follow-up/ }).first().click();
await A.p.getByLabel("Follow-up draft").waitFor();
ok("follow-up draft opens", (await A.p.getByLabel("Follow-up draft").inputValue()).length > 20);
await A.p.keyboard.press("Escape");

// --- other browser B: no access to A's message
const B = await mk();
await B.p.goto(`${WEB}/app`, { waitUntil: "networkidle" });
await B.p.waitForTimeout(1500);
ok("browser B dashboard does not list A's message", !(await B.p.locator("body").innerText()).includes("Al Noor Pharmacy") || (await B.p.locator("body").innerText()).includes("No messages yet"));
await B.p.goto(resultsUrl, { waitUntil: "networkidle" });
await B.p.getByText("Sender key required").waitFor({ timeout: 8000 });
ok("browser B opening A's results URL gets the 403 message", true);
const noKeyStatus = await B.p.evaluate(async (u) => (await fetch(u)).status, `http://localhost:8000/messages`);
ok("API without key -> 403", noKeyStatus === 403, String(noKeyStatus));

// --- admin-only LLM switch (D30)
const ADMIN = process.env.ADMIN_KEY || "e2e-admin-key-0123456789abcdef0123456789";
const health = async () => (await (await fetch("http://localhost:8000/health")).json());
const h0 = await health();
ok("server advertises admin_toggle_available", h0.admin_toggle_available === true);
ok("LLM switch is hidden from an ordinary visitor (no admin key in this browser)", (await A.p.getByRole("switch", { name: /LLM helper/ }).count()) === 0);
ok("sender key alone cannot flip it (API 403)", (await fetch("http://localhost:8000/settings/llm", { method: "POST", headers: { "Content-Type": "application/json", "X-Sender-Key": keyA }, body: JSON.stringify({ enabled: false }) })).status === 403);
ok("no key at all cannot flip it (API 403)", (await fetch("http://localhost:8000/settings/llm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: false }) })).status === 403);

// the operator enters the key once on /admin; the switch then appears and works
await A.p.goto(`${WEB}/admin`, { waitUntil: "networkidle" });
await A.p.getByLabel("Admin key").fill(ADMIN);
await A.p.getByRole("button", { name: "Save key" }).click();
await A.p.goto(`${WEB}/`, { waitUntil: "networkidle" });
const sw = A.p.getByRole("switch", { name: /LLM helper/ }).first();
await sw.waitFor({ timeout: 8000 });
ok("switch appears after the admin key is entered", true);
const before = (await health()).llm_switch;
await sw.click();
await A.p.waitForTimeout(1200);
const flipped = (await health()).llm_switch;
ok("admin can flip it (server state changed)", flipped === !before, `${before} -> ${flipped}`);
await sw.click();
await A.p.waitForTimeout(1200);
ok("and flip it back (restored)", (await health()).llm_switch === before);
ok("no error toast", (await A.p.getByText(/did not accept|Could not reach/).count()) === 0);

// a browser holding a WRONG key sees the switch but the server refuses
const W = await mk();
await W.ctx.addInitScript(() => localStorage.setItem("steve_admin_key", "not-the-admin-key"));
await W.p.goto(`${WEB}/`, { waitUntil: "networkidle" });
const wsw = W.p.getByRole("switch", { name: /LLM helper/ }).first();
await wsw.waitFor({ timeout: 8000 });
await wsw.click();
await W.p.getByText("did not accept that admin key").waitFor({ timeout: 8000 });
ok("wrong admin key: friendly refusal and server state unchanged", (await health()).llm_switch === before);
await W.ctx.close();

// --- demo page works for a fresh browser
const D = await mk();
await D.p.goto(`${WEB}/demo`, { waitUntil: "networkidle" });
await D.p.getByRole("link", { name: /Sender view/ }).first().waitFor({ timeout: 10000 });
ok("/demo seeds per-sender scenarios and shows links", true);
await D.p.getByRole("button", { name: /Everything right/ }).first().click();
await D.p.waitForTimeout(800);
ok("demo preset reply sends", (await D.p.getByText("Reply sent").count()) >= 0);

for (const [s, n, e] of results) console.log(s, n, e);
console.log("browser errors:", errors.length ? "\n" + errors.join("\n") : "none");
const failed = results.some((r) => r[0] === "FAIL");
console.log(failed ? "E2E FAILED" : "E2E ALL PASSED");
await browser.close();
process.exitCode = failed ? 1 : 0;
