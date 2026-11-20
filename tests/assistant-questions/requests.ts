/** Prints, as JSON, every question of the live banks a model reads on the hosted site and the requests the page sends for it (ADR-0121),
 * for the real-model run: `npx tsx tests/assistant-questions/requests.ts > requests.json`. Run from the repository's root. */
import { banks, modelRequests } from "./harness";

const out = banks().filter((bank) => !bank.waiting).flatMap((bank) => bank.questions.map((question, index) => ({
  id: `${bank.feature}#${index + 1}`, feature: bank.feature, ask: question.ask, page: question.page, route: question.route, live: question.live ?? null, mcp: question.mcp ?? null,
  gap: question.gap ?? null, requests: modelRequests(question),
}))).filter((q) => q.requests.length || q.mcp);
process.stdout.write(JSON.stringify(out, null, 1) + "\n");
