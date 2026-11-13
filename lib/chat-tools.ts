/** What the chat can work out (ADR-0055 amendment 3): one list the chat's first question is built from. A new capability is one
 * entry here with its own flow behind its own API endpoint; the chat only asks and shows, every number is the engine's (ADR-0001).
 * The coupon tests (ADR-0051) are the one tool with several entries of its own, `TEST_CHOICES` in `studio-chat.ts`. */
export type ChatToolId = "laminate" | "coupon";

export type ChatTool = {
  id: ChatToolId;
  title: string;
  /** One line under the title: what goes in and what comes out. */
  detail: string;
  /** Typed words that open the tool from the first question, or from inside another tool. */
  words: RegExp;
};

export const CHAT_TOOLS: readonly ChatTool[] = [
  {
    id: "laminate",
    title: "Laminate response",
    detail: "a stack under loads per unit width, no coupon: the ABD matrices, strains, every ply's stresses and first-ply failure in seconds, in the units you pick",
    words: /\b(laminate (response|problem|theory)|abd|classical lamination|hand calc|homework)\b/i,
  },
  {
    id: "coupon",
    title: "Coupon test",
    detail: "a test coupon set up, checked, solved by finite elements and verified, drawn ply by ply",
    words: /\b(coupon|open-hole|unnotched|bending|in-plane shear|plate|fea|finite element|calculix)\b/i,
  },
];

/** The tool a typed message names, or null when it names none. */
export function toolNamed(text: string): ChatToolId | null {
  const tool = CHAT_TOOLS.find((t) => t.words.test(text));
  return tool ? tool.id : null;
}

export function chatTool(id: ChatToolId): ChatTool {
  const tool = CHAT_TOOLS.find((t) => t.id === id);
  if (!tool) throw new Error(`no chat tool ${id}`);
  return tool;
}
