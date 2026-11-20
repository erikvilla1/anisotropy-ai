/** What the page shows once a real model has read each question (ADR-0121, the real-model run): reads the readers' answers that
 * `scripts/assistant-live.py` collected, and prints, as JSON, each question's answer as the chat shows it and what is wrong with it by its
 * bank. `npx tsx tests/assistant-questions/shown.ts readings.json`, from the repository's root. */
import { readFileSync } from "node:fs";
import { banks, liveFaults, modelAnswer, type Question, type Reading } from "./harness";

const readings = JSON.parse(readFileSync(process.argv[2], "utf8")) as { id: string; feature: string; ask: string; readings: Reading[] }[];
// a question is named by its bank and its place in it, as `requests.ts` names it
const questions = new Map<string, Question>(banks().flatMap((bank) => bank.questions.map((q, index) => [`${bank.feature}#${index + 1}`, q] as [string, Question])));
const out = readings.map((r) => {
  const question = questions.get(r.id);
  if (!question || question.ask !== r.ask) throw new Error(`${r.id}: “${r.ask}” is not that question of its bank; collect the readings again`);
  const said = modelAnswer(question, r.readings);
  return { id: r.id, feature: r.feature, ask: r.ask, said, faults: liveFaults(question, r.readings, said) };
});
process.stdout.write(JSON.stringify(out, null, 1) + "\n");
