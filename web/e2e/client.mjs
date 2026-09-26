// The typed TypeScript client (clients/ts/steve-client.ts) against the live API: compile it, then use decode / decodeAudio / clarify / health / examples like a
// separate front end would (D47). Run through `node e2e/run.mjs client`.
import ts from "typescript";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const src = fs.readFileSync(path.join(HERE, "..", "..", "clients", "ts", "steve-client.ts"), "utf8");
const js = ts.transpileModule(src, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ES2020 } }).outputText;
const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "steve-client-")), "steve-client.mjs");
fs.writeFileSync(tmp, js);
const { SteveClient, SteveApiError, newWorkerKey } = await import(pathToFileURL(tmp).href);

const API = "http://localhost:8000";
const MOCK = "http://127.0.0.1:9911";
const results = [];
const ok = (name, cond, extra = "") => results.push([cond ? "PASS" : "FAIL", name, extra]);
const steve = new SteveClient({ baseUrl: API + "/" });
ok("a worker key is generated when none is given", /^wk_[A-Za-z0-9_-]{24,}$/.test(steve.workerKey) && /^wk_/.test(newWorkerKey()));

const health = await steve.health();
ok("health(): typed and voice on, six languages", health.typed === true && health.voice === true && health.languages.length === 6, JSON.stringify(health.budget));
const ex = await steve.examples();
const quoz = ex.examples.find((e) => e.id === "al-quoz-maghrib");
ok("examples(): the Al Quoz / Maghrib sentence decodes from the live engine", quoz?.response.card.actions.where?.value === "al quoz" && quoz.response.card.actions.when?.value === "maghrib");

const r = await steve.decode({ text: "yalla habibi come to the barking gate tree", accentHint: "ar" });
ok("decode(): parking gate 3", r.card?.actions.where?.value === "parking gate 3" && r.decode_id === null);

const q = await steve.decode({ text: "come to the barking or the building?", accentHint: "ar" });
ok("decode(): an open question comes with a decode_id and no guess", !!q.decode_id && q.card?.clarify.length === 1 && q.card.actions.where === null);
const a = await steve.clarify({ decodeId: q.decode_id, questionIndex: 0, choice: "parking" });
ok("clarify(): resolved in place", a.card?.clarify.length === 0 && a.card.actions.where?.value === "parking" && a.decode_id === null);

const t = await steve.decode({ text: "come to the parking gate three at five", replyLanguage: "ml" });
ok("decode() with a reply language returns a checked translation", t.translation?.language === "ml" && t.translation.verified_numbers === true && t.translation.plain_english.includes("parking gate 3"), t.translation?.plain_english);

await fetch(`${MOCK}/__set`, { method: "POST", body: JSON.stringify({ transcript: "come to the gate free", sttFail: false }) });
const wav = new Uint8Array(44 + 32000);
const dv = new DataView(wav.buffer);
[..."RIFF"].forEach((c, i) => dv.setUint8(i, c.charCodeAt(0)));
dv.setUint32(4, 36 + 32000, true);
[..."WAVEfmt "].forEach((c, i) => dv.setUint8(8 + i, c.charCodeAt(0)));
dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, 16000, true); dv.setUint32(28, 32000, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true);
[..."data"].forEach((c, i) => dv.setUint8(36 + i, c.charCodeAt(0)));
dv.setUint32(40, 32000, true);
const v = await steve.decodeAudio(new Blob([wav], { type: "audio/wav" }), { accentHint: "ar" });
ok("decodeAudio(): transcript comes back and the voice path asks Three or free?", v.transcript === "come to the gate free" && v.card?.path === "voice" && v.card.clarify[0]?.question === "Three or free?");

let err;
try { await new SteveClient({ baseUrl: API, workerKey: "wk_short" }).decode({ text: "hi" }); } catch (e) { err = e; }
ok("a bad key raises SteveApiError with status 403", err instanceof SteveApiError && err.status === 403 && typeof err.detail === "string");
try { await steve.decode({ text: "" }); err = null; } catch (e) { err = e; }
ok("empty text raises SteveApiError 422", err instanceof SteveApiError && err.status === 422);
try { await steve.clarify({ decodeId: "not-a-real-id-xyz", questionIndex: 0, choice: "x" }); err = null; } catch (e) { err = e; }
ok("an unknown decode_id raises SteveApiError 404", err instanceof SteveApiError && err.status === 404);

for (const [s, n, e] of results) console.log(s, n, e);
const failed = results.some((x) => x[0] === "FAIL");
console.log(failed ? "CLIENT E2E FAILED" : "CLIENT E2E ALL PASSED");
process.exitCode = failed ? 1 : 0;
