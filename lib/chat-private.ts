/** What no chat sends to a model, on any page (ADR-0139): a key, a password or the hidden prompt asked for, and another person's work.
 * None of them is on a page, so the page answers them itself in fixed words before any model sees the message: the coupon chat through
 * `aboutAsked` (`lib/chat-about.ts`), the FEA assistant of a blank project through `routeStart` (`lib/work-intent.ts`). Pure, so the
 * tests run it in Node. Nothing here names a tool, a vendor or a model (ADR-0091). */

export type PrivateTopic = "instructions" | "others";

/** The hidden prompt asked for, or the rules asked to be dropped. */
const INSTRUCTIONS = /\b(?:system\s+prompt|your\s+(?:instructions|prompt|rules|guidelines|configuration|initial\s+prompt)|(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+|your\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|messages|prompts?|rules)|jailbreak|developer\s+mode)\b/i;
/** A key, a password or the hidden prompt asked for: none of them is on the page, and none is said. */
const SECRETS = /\b(?:api[\s_-]*keys?|passwords?|credentials?|secret\s+keys?|(?:access|auth(?:entication)?|bearer)\s+tokens?|env(?:ironment)?\s+(?:variables?|vars?)|hidden\s+(?:prompt|instructions|rules))\b/i;
/** Another person's work asked for ("the runs of the other users", "what did the previous user ask", "list every coupon in the
 * database"): a page holds only the engineer's own. The site's store asked for whole is someone else's work too; a material's own
 * library ("is IM7 in the material database?") is not asked for here, since it names no work. */
const OTHERS = /\b(?:other|another|previous|last|earlier|different)\s+(?:users?|persons?|people|customers?|accounts?|sign-?ins?)\b|\b(?:someone|somebody|anyone|anybody)\s+else\b|\b(?:everyone|everybody)(?:'s|’s)|\ball\s+(?:the\s+)?users\b|\bwho\s+else\b|\bemails?\s+(?:address\s+)?of\b|\b(?:every|all)\s+(?:the\s+)?(?:coupons?|runs?|analys[ie]s|projects?|models?|jobs?|files?|results?|records?|chats?|conversations?)\b[^.?!\n]{0,30}\b(?:database|db|server|site)\b/i;

/** The topic a message asks about, when it is one no model is shown, or null. */
export function privateAsked(text: string): PrivateTopic | null {
  if (INSTRUCTIONS.test(text) || SECRETS.test(text)) return "instructions";
  if (OTHERS.test(text)) return "others";
  return null;
}

/** Each topic's heading, the same on every page. */
export const PRIVATE_TITLES: Record<PrivateTopic, string> = { instructions: "Not something I share", others: "Only your own work" };

/** What another person's work asked for is answered with, under its heading. */
export const OTHERS_LINES = [
  "This chat sees the page you have open and nothing of anyone else's: no other person's analyses, questions or sign-in.",
  "Your own past analyses are under “Your analyses” on the start page.",
];

/** The answer of the FEA assistant of a blank project, where nothing is set up yet: the heading and what can be asked there instead. */
export function privateAnswerOnStart(topic: PrivateTopic): { title: string; lines: string[] } {
  return topic === "others" ? { title: PRIVATE_TITLES.others, lines: OTHERS_LINES }
    : { title: PRIVATE_TITLES.instructions, lines: [
      "Ask about finite element analysis instead, for example “What is a mesh convergence study?”, or say what to set up: “I want to test some coupons”."] };
}
