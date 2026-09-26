// Starts everything a browser test needs and tears it down again (D45):
//   * a MOCK of the Sarvam API on :9911 (speech-to-text and translate), so the real client code runs without the internet or a key;
//   * the API (uvicorn) on :8000 with a throw-away database, no LLM, the mock as Sarvam, and an admin key;
//   * the production web build (`next start`) on :3000.
// Run `npm run build` first. Ports 3000, 8000 and 9911 must be free. Used by e2e/run.mjs.
import { spawn, spawnSync } from "node:child_process";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const WEB_DIR = path.resolve(HERE, "..");
export const ROOT = path.resolve(WEB_DIR, "..");
export const WEB = "http://localhost:3000";
export const API = "http://localhost:8000";
export const MOCK = "http://127.0.0.1:9911";
export const ADMIN_KEY = "e2e-admin-key-0123456789abcdef0123456789";

const PY = path.join(ROOT, ".venv", "Scripts", "python.exe");

/** The mock Sarvam: `POST /__set` changes what it returns, `GET /__log` shows what it was asked (no audio bytes). */
function startMock() {
  const state = { transcript: "come to the barking or the building", translateMode: "prefix", calls: [] };
  const server = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const body = Buffer.concat(chunks);
      const json = (o, code = 200) => { res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(o)); };
      if (req.url === "/__set") { Object.assign(state, JSON.parse(body.toString() || "{}")); return json({ ok: true }); }
      if (req.url === "/__log") return json(state.calls);
      if (req.url === "/speech-to-text") {
        const text = body.toString("latin1");
        state.calls.push({ kind: "stt", mode: /name="mode"\r\n\r\n(\w+)/.exec(text)?.[1], lang: /name="language_code"\r\n\r\n([\w-]+)/.exec(text)?.[1], bytes: body.length });
        if (state.sttFail) return json({ error: "mock failure" }, 500);
        return json({ request_id: "mock", transcript: state.transcript, language_code: "en-IN" });
      }
      if (req.url === "/translate") {
        const inp = JSON.parse(body.toString());
        state.calls.push({ kind: "translate", target: inp.target_language_code, chars: inp.input.length });
        let out = `[${inp.target_language_code}] ${inp.input}`;
        if (state.translateMode === "mangle") out = out.replace(/\d+/g, (d) => String(Number(d) + 5));
        if (state.translateMode === "fail") return json({ error: "mock failure" }, 500);
        return json({ request_id: "mock", translated_text: out, source_language_code: "en-IN" });
      }
      json({ error: "not found" }, 404);
    });
  });
  return new Promise((resolve) => server.listen(9911, "127.0.0.1", () => resolve({ server, state })));
}

async function waitFor(url, ms = 60000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { const r = await fetch(url); if (r.status < 500) return; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`timed out waiting for ${url}`);
}

function kill(child) {
  if (child?.pid) spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
}

export async function startStack({ extraApiEnv = {} } = {}) {
  for (const [name, url] of [["web", WEB], ["api", `${API}/health`]]) {
    try { await fetch(url); throw new Error(`${name} is already running on its port; stop it first`); } catch (e) { if (/already running/.test(e.message)) throw e; }
  }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "steve-e2e-"));
  const { server, state } = await startMock();
  const env = {
    ...process.env, DATABASE_URL: `sqlite:///${path.join(tmp, "e2e.db").replace(/\\/g, "/")}`, LLM_ENABLED: "false", GEMINI_API_KEY: "", ADMIN_KEY,
    SARVAM_API_KEY: "e2e-fake-sarvam-key", SARVAM_BASE_URL: MOCK, CORS_ORIGINS: WEB, PUBLIC_WEB_URL: WEB, TRUST_PROXY: "false",
    RL_MESSAGES_PER_MIN: "1000", RL_MESSAGES_PER_DAY: "10000", RL_MESSAGES_PER_SENDER_DAY: "10000", RL_CHECK_PER_MIN: "1000", RL_DEFAULT_PER_MIN: "10000",
    RL_DECODE_PER_MIN: "1000", RL_DECODE_PER_DAY: "10000", DECODE_PER_WORKER_DAY: "10000", REPLY_RATE_LIMIT: "1000", ...extraApiEnv,
  };
  const api = spawn(PY, ["-m", "uvicorn", "app.main:app", "--port", "8000", "--log-level", "warning"], { cwd: path.join(ROOT, "api"), env, stdio: ["ignore", "inherit", "inherit"] });
  const web = spawn(process.execPath, [path.join(WEB_DIR, "node_modules", "next", "dist", "bin", "next"), "start", "-p", "3000"], { cwd: WEB_DIR, env: { ...process.env }, stdio: ["ignore", "inherit", "inherit"] });
  const stop = () => { kill(api); kill(web); server.close(); fs.rmSync(tmp, { recursive: true, force: true }); };
  try {
    await waitFor(`${API}/health`);
    await waitFor(WEB);
  } catch (e) { stop(); throw e; }
  return { stop, mock: state, setMock: (o) => fetch(`${MOCK}/__set`, { method: "POST", body: JSON.stringify(o) }) };
}
