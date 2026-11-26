/**
 * The words that tell a question from a request, and a request for an answer, in every chat of the workspace: the coupon's
 * (`lib/chat-route.ts`), the wing's (`lib/wing-chat.ts`) and the repair's (`lib/repair-chat.ts`). They decide whether a sentence goes to
 * the planner (ADR-0144); nothing here answers. Pure, so each chat's tests hold them.
 */

/** A message that asks rather than tells (ADR-0121 amendment 2): it opens with a word that asks ("what", "how", "is", "does", "should"),
 * or it ends in a question mark and asks for nothing to be done ("can you make it 30 wide?" is a request, and is read as one). "What
 * about" and "how about" offer a value, so they are no question. A question is never read into rows of the setup: "how did you get
 * 16740 N" changes no load. */
const ASKS_OPEN = /^\s*(?:why|what(?!\s+about\b)|where|which|who|whom|whose|when|how(?!\s+about\b)|compare|is|are|was|were|does|should|shall|am|(?:do|did|have|has)(?=\s+(?:you|u|i|we|they|it|this|my|the)\b))\b/i;
const REQUEST = /^\s*(?:please|(?:can|could|would|will)\s+(?:you|u|we|i)|may\s+i|let'?s|i(?:'d|\s+would)\s+like|i\s+want)\b/i;
export const isQuestion = (text: string): boolean => ASKS_OPEN.test(text) || (/\?\s*$/.test(text) && !REQUEST.test(text));

/** An answer asked for in words, beside a change: "tell me if it holds", "let me know the lowest margin", "see whether the slice holds it". */
export const ANSWERS = new RegExp([
  /\b(?:tell|show|give)\s+me\b|\blet\s+me\s+know\b/.source,
  /\b(?:see|check|find\s+out|determine|work\s+out|find|report)\s+(?:if|whether|how|what|which|where)\b/.source,
  /\b(?:does|will|would|whether|if)\s+it\s+(?:holds?|fails?|breaks?|survives?|pass(?:es)?|yields?)\b/.source,
  /\bfirst[- ]ply[- ]failure\b|\bfpf\b/.source,
].join("|"), "i");

/** A sentence cut where a new ask begins, so each part is read alone: at a comma or a semicolon, at "then", and at "and" before a verb
 * that asks for something to be done. "between 3 and 25 mm" stays whole. */
export function clauses(text: string, verbs: string): string[] {
  const and = new RegExp(String.raw`\s*(?:[,;]\s*(?:and\s+)?(?:then\s+)?|\s+and\s+then\s+|\s+then\s+|\s+and\s+(?=(?:please\s+)?(?:${verbs})\b))`, "i");
  return text.split(and).map((part) => part.trim()).filter(Boolean);
}
