#!/usr/bin/env node
// The rule of ADR-0121: a pull request that changes how the assistant reads or answers a question adds the questions that try it to a
// bank in tests/assistant-questions/, or says in its description why none are needed, on a line that starts "Assistant questions: none
// needed" and gives the reason. The files that count are the assistant's own (below) and every file a bank watches.
//
//   node scripts/assistant-questions-check.mjs --base origin/main        (the description is read from PR_BODY)
//
// It reads git and the banks only; it needs no install.
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const FOLDER = "tests/assistant-questions";
// The assistant itself, whatever bank a change touches: the chat, its routing, the API's model readers and every tool of the MCP server.
const ASSISTANT = [
  "components/studio/coupon-chat.tsx", "components/studio/laminate-chat.tsx", "lib/chat-route.ts", "api/src/anisotropy_api/assistant.py",
  "api/src/anisotropy_api/result_questions.py", "api/src/anisotropy_api/result_answers.py", "api/src/anisotropy_api/proposals.py",
  "api/src/anisotropy_api/plate_proposals.py", "api/src/anisotropy_api/theory.py", "mcp-server/src/",
];
const EXCUSE = /^\s*Assistant questions:\s*none needed\s*[-:—–]+\s*(.{12,})$/im;

const arg = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const base = arg("--base", "origin/main");
const changed = execFileSync("git", ["diff", "--name-only", `${base}...HEAD`], { encoding: "utf8" }).split("\n").filter(Boolean);

const banks = readdirSync(FOLDER).filter((name) => name.endsWith(".json")).map((name) => JSON.parse(readFileSync(join(FOLDER, name), "utf8")));
const watchedBy = (path) => banks.filter((bank) => bank.watches.includes(path)).map((bank) => bank.feature);
const touched = changed.map((path) => ({ path, banks: watchedBy(path), own: ASSISTANT.some((a) => a.endsWith("/") ? path.startsWith(a) : path === a) }))
  .filter((t) => t.own || t.banks.length);
const asked = changed.filter((path) => path.startsWith(`${FOLDER}/`) && path.endsWith(".json"));

if (!touched.length) {
  console.log("No file of the assistant changed: no questions needed.");
  process.exit(0);
}
console.log("Files of the assistant this pull request changes:");
for (const t of touched) console.log(`  ${t.path}${t.banks.length ? `  (bank: ${t.banks.join(", ")})` : ""}`);
if (asked.length) {
  console.log(`\nQuestions changed: ${asked.join(", ")}. The rule holds; the banks' own tests judge the questions.`);
  process.exit(0);
}
const excuse = (process.env.PR_BODY ?? "").match(EXCUSE);
if (excuse) {
  console.log(`\nNo bank changed, and the description says why: “${excuse[1].trim()}”.`);
  process.exit(0);
}
const named = [...new Set(touched.flatMap((t) => t.banks))];
console.log(`\nNo question was added or changed. Add the questions a user would ask of this change to ${named.length ? named.map((f) => `${FOLDER}/${f}.json`).join(" or ") : `a bank in ${FOLDER}/`}`
  + " (the chat-answer-quality skill says how), or write in the pull request's description a line such as"
  + " “Assistant questions: none needed — the change renames a variable and answers nothing new”.");
process.exit(1);
