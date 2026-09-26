// `node e2e/run.mjs [check|listen|client|all]`: start the stack (mock Sarvam, API, production web), run the browser flow scripts, stop everything.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startStack, ADMIN_KEY } from "./stack.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const which = process.argv[2] || "all";
const scripts = { check: ["check-mode.mjs"], listen: ["listen.mjs"], client: ["client.mjs"], all: ["check-mode.mjs", "listen.mjs", "client.mjs"] }[which];
if (!scripts) { console.error("usage: node e2e/run.mjs [check|listen|client|all]"); process.exit(2); }

// async spawn on purpose: the mock Sarvam server lives in THIS process and must keep answering while a script runs
const run = (file) => new Promise((resolve) => {
  const child = spawn(process.execPath, [file], { cwd: path.join(HERE, ".."), env: { ...process.env, ADMIN_KEY }, stdio: "inherit" });
  child.on("exit", (code) => resolve(code ?? 1));
});

const stack = await startStack();
let failed = false;
try {
  for (const s of scripts) {
    const file = path.join(HERE, s);
    if (!fs.existsSync(file)) { console.log(`(skipping ${s}: not written yet)`); continue; }
    console.log(`\n=== ${s} ===`);
    if ((await run(file)) !== 0) failed = true;
  }
} finally {
  stack.stop();
}
console.log(failed ? "\nBROWSER FLOWS FAILED" : "\nBROWSER FLOWS PASSED");
process.exit(failed ? 1 : 0);
