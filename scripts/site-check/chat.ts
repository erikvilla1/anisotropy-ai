/** Asking a question in whichever chat the page shows, and reading the answer as an engineer sees it (ADR-0138): the coupon's chat, the
 * FEA start, the wing's and the repair's all write the engineer's message as `.chat-user` and each answer as `.chat-assistant`, with
 * `.chat-typing` while they work, the answer's heading as its first heading and what is folded under `<details>`. */
import type { Locator, Page } from "@playwright/test";

/** The message box of every chat ("Message the coupon assistant", "Message the FEA assistant", ...). */
export const BOX = "textarea[aria-label^='Message the']";

/** What the page shows for one question, read from the chat's own elements. */
export type Answer = { heading: string; shown: string; folded: string; parts: string[]; applies: boolean };
/** `interim`: the first answer shown, when the page then replaced it with another (a sweep or a solve the page works on after it says so).
 * `busy`: what the page said it was still doing when the robot stopped waiting ("Checking the setup…"), its answer shown above it. */
export type Asked = Answer & { seconds: number; timedOut: boolean; interim?: Answer; busy?: string };
type Probe = { label: string | null; sent: boolean; typing: boolean; busy: string; answers: number; answer: Answer };

/** The chat's state, read in the page. The answers are those after the engineer's message `asked`, the `n`-th or a later one, in the chat
 * whose box is labelled `label`; when the page has put another chat in its place (the FEA start setting up a coupon), every answer of
 * the new chat is the answer. */
function probe(args: { selector: string; asked: string; n: number; label: string }): Probe {
  const empty = { heading: "", shown: "", folded: "", parts: [] as string[], applies: false };
  const box = [...document.querySelectorAll<HTMLTextAreaElement>(args.selector)].find((el) => el.offsetParent !== null);
  if (!box) return { label: null, sent: false, typing: false, busy: "", answers: 0, answer: empty };
  const label = box.getAttribute("aria-label");
  const root = box.closest("[data-testid$='chat']") ?? box.closest("section") ?? document.body;
  const items = [...root.querySelectorAll<HTMLElement>(".chat-user, .chat-assistant")];
  let after: HTMLElement[];
  if (label === args.label) {
    const users = items.filter((el) => el.classList.contains("chat-user"));
    const mine = users.slice(args.n).find((el) => (el.textContent ?? "").trim() === args.asked.trim());
    if (!mine) return { label, sent: false, typing: false, busy: "", answers: 0, answer: empty };
    after = items.slice(items.indexOf(mine) + 1);
    const next = after.findIndex((el) => el.classList.contains("chat-user"));
    if (next >= 0) after = after.slice(0, next);
  } else {
    after = items;
  }
  const answers = after.filter((el) => el.classList.contains("chat-assistant") && (!el.querySelector(".chat-typing") || (el.textContent ?? "").trim().length > 40));
  const typing = !!root.querySelector(".chat-typing");
  const busy = (root.querySelector(".chat-typing")?.textContent ?? "").trim();
  const heading = answers.map((el) => el.querySelector("h2, h3, h4")?.textContent?.trim() ?? "").find(Boolean) ?? "";
  // A closed fold is not drawn, so its innerText is its bare text, which runs a table's cells together ("74" "12.85" "233.5" read as
  // 7412.85233.5): its text is walked instead, with a space between cells and a line between blocks. No named function is declared in
  // here: the page runs this function's text alone, without the helpers a compiler adds for names.
  const folded: string[] = [];
  for (const el of answers) {
    for (const d of el.querySelectorAll("details")) {
      let out = "";
      const stack: (Node | string)[] = [d];
      while (stack.length) {
        const node = stack.pop()!;
        if (typeof node === "string") { out += node; continue; }
        if (node.nodeType === Node.TEXT_NODE) { out += (node as Text).data; continue; }
        if (node.nodeType !== Node.ELEMENT_NODE || (node as Element).tagName === "SUMMARY") continue;
        const tag = (node as Element).tagName;
        const gap = tag === "TD" || tag === "TH" ? " " : /^(P|LI|TR|DIV|TABLE|UL|OL|BR|H[1-6])$/.test(tag) ? "\n" : "";
        stack.push(gap, ...[...node.childNodes].reverse(), gap);
      }
      folded.push(out.replace(/[ \t]+/g, " ").replace(/ *\n\s*/g, "\n").trim());
    }
  }
  const parts = new Set<string>(label === args.label ? [] : ["another-chat"]);
  for (const el of answers) {
    for (const tagged of [el, ...el.querySelectorAll<HTMLElement>("[data-testid], [data-kind]")]) {
      if (tagged.dataset.testid) parts.add(tagged.dataset.testid);
      if (tagged.dataset.kind) parts.add(`kind:${tagged.dataset.kind}`);
    }
  }
  const applies = answers.some((el) => !!el.querySelector(".proposal-card input[type=checkbox]")
    || [...el.querySelectorAll("button")].some((b) => /^\s*Apply\b/.test(b.textContent ?? "")));
  return { label, sent: true, typing, busy, answers: answers.length,
    answer: { heading, shown: answers.map((el) => el.innerText.trim()).join("\n"), folded: folded.join("\n"), parts: [...parts], applies } };
}

/** The chat box the page shows now, or null. */
export async function chatBox(page: Page): Promise<Locator | null> {
  const box = page.locator(BOX).filter({ visible: true }).first();
  return (await box.count()) ? box : null;
}

/** Sends a message and waits for its answer to stand still: nothing typing and the same text for `still` ms. A message that opens
 * another page is answered by that page: "The page opened /workspace/repair." `timedOut` when nothing stood still in `limit` ms. */
export async function ask(page: Page, text: string, limit: number, still = 900): Promise<Asked> {
  const box = await chatBox(page);
  if (!box) throw new Error("no chat box on the page");
  const label = (await box.getAttribute("aria-label")) ?? "";
  const n = await box.evaluate((el) => (el.closest("[data-testid$='chat']") ?? el.closest("section") ?? document.body).querySelectorAll(".chat-user").length);
  const from = new URL(page.url()).pathname;
  await box.fill(text);
  const started = Date.now();
  await box.press("Enter");
  let last = "";
  let since = Date.now();
  let seen: Probe | null = null;
  let first: Answer | null = null;
  let firstAt = 0;
  const withFirst = (answer: Answer) => (first && first.heading !== answer.heading ? { interim: first } : {});
  while (Date.now() - started < limit) {
    await page.waitForTimeout(250);
    const path = new URL(page.url()).pathname;
    if (path !== from) { // another page: that is the answer, once it has loaded
      await page.waitForLoadState("domcontentloaded").catch(() => undefined);
      return { heading: "", shown: `The page opened ${path}.`, folded: "", parts: ["opened-page"], applies: false, seconds: (Date.now() - started) / 1000, timedOut: false };
    }
    let now: Probe;
    try {
      now = await page.evaluate(probe, { selector: BOX, asked: text, n, label });
    } catch {
      continue; // the page is between two states
    }
    seen = now;
    if (!first && now.sent && now.answers > 0 && now.answer.heading) { first = now.answer; firstAt = Date.now(); }
    const shape = JSON.stringify(now.answer) + now.typing;
    if (shape !== last) { last = shape; since = Date.now(); continue; }
    if (now.sent && !now.typing && now.answers > 0 && Date.now() - since >= still) {
      return { ...now.answer, ...withFirst(now.answer), seconds: (since - started) / 1000, timedOut: false };
    }
  }
  const answer = seen?.answer ?? { heading: "", shown: "", folded: "", parts: [], applies: false };
  // an answer shown, and the page still at work under it when the limit passed ("Checking the setup…"): timed from when it was shown
  const busy = seen?.typing && seen.busy && first ? { busy: seen.busy, seconds: (firstAt - started) / 1000 } : null;
  return { ...answer, ...withFirst(answer), seconds: (Date.now() - started) / 1000, timedOut: true, ...(busy ?? {}) };
}

/** The chat's whole pane, for a picture of an answer. */
export async function chatPane(page: Page): Promise<Locator | null> {
  const box = await chatBox(page);
  if (!box) return null;
  let pane = box.locator("xpath=ancestor::*[contains(@data-testid,'chat')][1]");
  if (!(await pane.count())) return null;
  // The wing's and the repair's chats draw no box of their own in the workspace (display: contents): the panel they sit in is pictured.
  for (let up = 0; up < 4 && !(await pane.boundingBox()); up++) pane = pane.locator("xpath=..");
  return (await pane.boundingBox()) ? pane : null;
}

/** The text of the page outside the chat: the results card, the tables, the model tree. Its numbers are the page's own. */
export async function pageText(page: Page): Promise<string> {
  return page.evaluate((selector) => {
    const box = [...document.querySelectorAll<HTMLTextAreaElement>(selector)].find((el) => el.offsetParent !== null);
    const root = box?.closest("[data-testid$='chat']") as HTMLElement | null | undefined;
    const all = document.body.innerText;
    return root ? all.replace(root.innerText, "") : all;
  }, BOX);
}
