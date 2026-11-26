/** Which questions a run of the site check asks, in what order, and which it leaves out and why (ADR-0138). The questions are the banks'
 * (ADR-0121): one list for the check that runs free on every pull request, the real-model check before a feature merges, and this one on
 * the live site. */
import { banks, modelRequests, pageGap, type Bank, type Page, type Question } from "../../tests/assistant-questions/harness";

/** "quick", after a deploy: only the questions the page answers by itself, which cost nothing on the site. "full", every few days: every
 * question, the model's too, until the run's cap. */
export type Mode = "quick" | "full";

export type Planned = {
  /** The question's name in every report, as the real-model check names it: the bank's feature and its place in the bank. */
  id: string;
  feature: string;
  question: Question;
  /** Whether the site reads it with a model (the page sends it to the API's readers), so it costs and its answer is the model's. */
  modelRead: boolean;
};
export type Skipped = { id: string; feature: string; ask: string; page: Page; reason: string; question: Question };

/** The pages a customer's sign-in reaches, in the order a run sets them up: each group of questions is asked on one page. A service token
 * is a customer's view (no founder's features), so the founder's pages are left out with the reason. */
export const PAGES_IN_ORDER: readonly Page[] = ["start", "blank", "setup", "ready", "results", "past", "wing", "wing-caps", "repair", "repair-solved", "repair-external"];
export const NOT_OFFERED: Partial<Record<Page, string>> = {
  plate: "a plate is set up on a founder's sign-in only, and the check signs in as a customer",
  imported: "a model is imported on a founder's sign-in only, and the check signs in as a customer",
  "repair-plies": "carrying a repair until it cannot hold the load is a job of minutes that counts against a sign-in's jobs for the day: the check starts none",
};

/** A full run's planner questions (ADR-0144, step 4): each keeps its page's project on the site, so the site can plan on it, and asks
 * the site's model for a plan, which the robot reads and never approves. A few a run, on the pages a customer plans from, taking turns. */
export const PLANS_PER_RUN = 3;
export const PLAN_PAGES: readonly Page[] = ["setup", "ready"];

/** Routes that move the page on (a new coupon, a run, another page opened): asked last on their page, after which the page is set up again. */
const MOVES: ReadonlySet<string> = new Set(["start-over", "run", "check", "full-form", "set-up", "open", "section", "wing-command", "repair-command"]);

/** The questions of a run. In a full run the questions the site reads with a model take turns: at most `slots` of them, those asked
 * longest ago first (`lastAsked`, by id, an ISO time), so a cap too small for all of them still reaches each within a few runs. */
export function plan(mode: Mode, features: readonly string[] = [], from: readonly Bank[] = banks(),
  turns: { slots: number; lastAsked: Readonly<Record<string, string>> } = { slots: Infinity, lastAsked: {} }): { asked: Planned[]; skipped: Skipped[] } {
  const asked: Planned[] = [];
  const skipped: Skipped[] = [];
  const wanted = new Set(features.map((f) => f.trim()).filter(Boolean));
  const known = new Set(from.map((b) => b.feature));
  const unknown = [...wanted].filter((f) => !known.has(f));
  if (unknown.length) throw new Error(`no bank named ${unknown.join(", ")}`);
  for (const bank of from) {
    if (wanted.size && !wanted.has(bank.feature)) continue;
    // a bank may ask the same words twice, with the Ansys file offered and without: the site offers it to everyone (ADR-0129 amendment 3)
    const ansysTwins = new Set(bank.questions.filter((q) => q.ansys === true).map((q) => `${q.ask.trim().toLowerCase()}|${q.after?.join("|") ?? ""}`));
    bank.questions.forEach((question, index) => {
      const id = `${bank.feature}#${index + 1}`;
      const skip = (reason: string) => skipped.push({ id, feature: bank.feature, ask: question.ask, page: question.page, reason, question });
      if (bank.waiting) return skip(`the bank waits for its feature: ${bank.waiting}`);
      const offered = NOT_OFFERED[question.page];
      if (offered) return skip(offered);
      if (question.picked !== undefined) return skip("it is asked about an element clicked on the model, which the check does not click");
      if (question.asking !== undefined) return skip("it answers the chat's own question in the middle of a setup");
      if (question.ansys !== true && ansysTwins.has(`${question.ask.trim().toLowerCase()}|${question.after?.join("|") ?? ""}`)) {
        return skip("it is asked of a page without the Ansys file, which the site offers to everyone: its twin with the file offered is asked");
      }
      if (question.route === "plan") { // ADR-0144, step 4
        if (mode === "quick") return skip("a plan keeps the project on the site and asks its model: a quick run keeps no projects and spends nothing, so it is asked in the full run");
        if (!PLAN_PAGES.includes(question.page)) return skip(`a plan is asked on the ${PLAN_PAGES.join(" and ")} pages only, where setting up the page starts no analysis`);
        if (pageGap(question)) return skip(`the page does not plan it yet (a known gap): ${question.gap}`);
      }
      const modelRead = modelRequests(question).length > 0;
      if (mode === "quick" && modelRead) return skip("a model reads it on the site: asked in the full run");
      if (mode === "quick" && (question.route === "run" || question.page === "results")) { // ADR-0138 amendment 3
        return skip("it needs an analysis run on the site: a quick run leaves the day's analyses of the check's sign-in to the deploy check, so it is asked in the full run");
      }
      asked.push({ id, feature: bank.feature, question, modelRead });
    });
  }
  const longestAgo = (a: { p: Planned; i: number }, b: { p: Planned; i: number }) =>
    (turns.lastAsked[a.p.id] ?? "").localeCompare(turns.lastAsked[b.p.id] ?? "") || a.i - b.i;
  const plans = asked.filter((p) => p.question.route === "plan").map((p, i) => ({ p, i })).sort(longestAgo);
  for (const { p } of plans.slice(PLANS_PER_RUN)) { // a few plans a run, those asked longest ago first
    asked.splice(asked.indexOf(p), 1);
    skipped.push({ id: p.id, feature: p.feature, ask: p.question.ask, page: p.question.page, question: p.question,
      reason: `its turn comes in a later full run: a full run asks ${PLANS_PER_RUN} plans at most` });
  }
  const models = asked.filter((p) => p.modelRead);
  if (models.length > turns.slots) {
    const order = models.map((p, i) => ({ p, i })).sort(longestAgo);
    const waiting = new Set(order.slice(Math.max(0, turns.slots)).map(({ p }) => p));
    for (const p of waiting) {
      asked.splice(asked.indexOf(p), 1);
      skipped.push({ id: p.id, feature: p.feature, ask: p.question.ask, page: p.question.page, question: p.question,
        reason: "its turn comes in a later full run: the questions a model reads take turns under the run's cap" });
    }
  }
  const rank = (p: Planned) => PAGES_IN_ORDER.indexOf(p.question.page) * 4 + (p.question.after?.length ? 1 : 0) + (MOVES.has(p.question.route) ? 2 : 0);
  return { asked: asked.map((p, i) => ({ p, i })).sort((a, b) => rank(a.p) - rank(b.p) || a.i - b.i).map(({ p }) => p), skipped };
}

/** Routes whose answer changes the page's rows at once ("switch to inches", a name): a later question would be asked of another coupon
 * than its bank's, so the page is set up again after it (the second run asked "what units are you using?" after "work in metres"). A plan
 * changes nothing until it is approved, but its question back would take the next message as its answer, and its card draws on the model. */
const CHANGES: ReadonlySet<string> = new Set(["patterns", "name", "plan"]);

/** Whether a question's route may move the page on or change its rows, so the page is checked and set up again after it. */
export const moves = (question: Question): boolean => MOVES.has(question.route) || CHANGES.has(question.route);
