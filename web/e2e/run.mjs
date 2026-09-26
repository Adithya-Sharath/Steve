// `node e2e/run.mjs [check|listen|all]`: start the stack (mock Sarvam, API, production web), run the browser flow scripts, stop everything.
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startStack, ADMIN_KEY } from "./stack.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const which = process.argv[2] || "all";
const scripts = { check: ["check-mode.mjs"], listen: ["listen.mjs"], landing: ["landing.mjs"], all: ["check-mode.mjs", "listen.mjs", "landing.mjs"] }[which];
if (!scripts) { console.error("usage: node e2e/run.mjs [check|listen|landing|all]"); process.exit(2); }

const stack = await startStack();
let failed = false;
try {
  for (const s of scripts) {
    const file = path.join(HERE, s);
    try { (await import("node:fs")).accessSync(file); } catch { console.log(`(skipping ${s}: not written yet)`); continue; }
    console.log(`\n=== ${s} ===`);
    const r = spawnSync(process.execPath, [file], { cwd: path.join(HERE, ".."), env: { ...process.env, ADMIN_KEY }, stdio: "inherit" });
    if (r.status !== 0) failed = true;
  }
} finally {
  stack.stop();
}
console.log(failed ? "\nBROWSER FLOWS FAILED" : "\nBROWSER FLOWS PASSED");
process.exit(failed ? 1 : 0);
