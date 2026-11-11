/** The load-in moves (ADR-0070 amendment 1), after Anduril's, for any element that carries `data-intro`:
 *
 *   data-intro="type"  the text is typed in, line by line, each new character first shown as random letters;
 *   data-intro="rise"  each line of the text rises out from behind its own bottom edge (for a big heading);
 *   data-intro="fade"  the element fades in while it moves up 15% of its height (for an image or a block);
 *   data-intro-delay   milliseconds after the black starts to lift, to override the order below.
 *
 * Without a delay: a rise starts with the lift, a fade 100 ms later, and typed lines start 150 ms after the lift, one every
 * 100 ms in document order. The page's own text is never changed, moved or removed: it is only made transparent while a copy,
 * absolutely placed over it and hidden from assistive technology, plays the move, so nothing re-wraps and a screen reader
 * reads the text once. The copy goes when the move ends. Only elements in the viewport take part.
 *
 * Every move is a transform or opacity animation, which the browser keeps running while the page's scripts are busy; no
 * script runs between the start and the end. A typed line is seen through a window whose right edge steps from character to
 * character. A second window, between that edge and where it was 110 ms before, shows random letters in the characters'
 * places; they change 20 times a second. */

const EASE_OUT_EXPO = "cubic-bezier(0.19, 1, 0.22, 1)"; // Anduril's "easeOutExpo", as its stylesheet table gives it
const RISE_MS = 1500; // Anduril's page heading: 100% to its place in 1500 ms
const FADE_MS = 1500; // Anduril's image and text columns: 1500 ms
const FADE_SHIFT = "15%"; // Anduril's image starts 15% of its height low
const FADE_DELAY_MS = 100;
const TYPE_DELAY_MS = 150; // measured: the first character shows about 130 to 150 ms after the black starts to lift
const LINE_STAGGER_MS = 100; // measured: each line starts about 100 ms after the one above; Anduril's code staggers by 100 ms
const TYPE_CHARS_PER_S = 38; // measured: 17 to 21 characters of a line appear in about 0.5 s
const LINE_MAX_MS = 530; // measured: a line is all on screen about 0.53 s after its first character
const SETTLE_MS = 110; // measured: a character is random letters for about 3 to 4 characters' time before it settles
const SCRAMBLE_TICK_MS = 50; // Anduril redraws its random letters 20 times a second

// Random letters of about the real letter's width, so they sit in its place: narrow for narrow, and never the widest.
const NARROW = "iljtfrIJ1";
const LETTERS = { upper: "ABCDEFGHKLNOPQRSTUVXYZ", lower: "abcdeghknopqsuvxyz", narrowUpper: "IJ", narrowLower: "ijltfr", digits: "0123456789" };

export type IntroRun = {
  /** Start the moves; call it in the frame the black starts to lift. */
  play: () => void;
  /** End now: remove every copy and show the page's own text. Safe to call twice. */
  finish: () => void;
  /** How long the moves take from play(), in ms. */
  totalMs: number;
};

type Kind = "type" | "rise" | "fade";
type Piece = { parent: Element; text: string };
type MeasuredLine = { pieces: Piece[]; first: DOMRect };
type Move = { element: HTMLElement; keyframes: Keyframe[]; options: KeyframeAnimationOptions };

const pick = (from: string) => from[Math.floor(Math.random() * from.length)];
/** A random letter of the same case and about the same width, a random digit for a digit; spaces and punctuation stay. */
function scrambled(char: string) {
  const narrow = NARROW.includes(char);
  if (char >= "A" && char <= "Z") return pick(narrow ? LETTERS.narrowUpper : LETTERS.upper);
  if (char >= "a" && char <= "z") return pick(narrow ? LETTERS.narrowLower : LETTERS.lower);
  if (char >= "0" && char <= "9") return pick(LETTERS.digits);
  return char;
}

/** The element's text as the browser has laid it out: one entry per line, each a list of runs of text with the inline element
 * that holds them, and the place of the line's first word. Null when the text keeps its own spaces (`white-space: pre…`) or
 * nothing is laid out. */
function measureLines(element: HTMLElement): MeasuredLine[] | null {
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  const lines: MeasuredLine[] = [];
  let line: MeasuredLine | null = null;
  let gap = false; // white space since the last word
  for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
    const parent = node.parentElement;
    if (!parent) continue;
    if (getComputedStyle(parent).whiteSpace.startsWith("pre")) return null;
    const words = /\S+/g;
    let end = 0;
    for (let match = words.exec(node.data); match; match = words.exec(node.data)) {
      if (match.index > end) gap = true;
      end = match.index + match[0].length;
      range.setStart(node, match.index);
      range.setEnd(node, end);
      const rect = range.getClientRects()[0];
      if (!rect || (rect.width === 0 && rect.height === 0)) continue;
      const middle = (rect.top + rect.bottom) / 2;
      if (!line || middle < line.first.top || middle > line.first.bottom) {
        line = { pieces: [], first: rect };
        lines.push(line);
        gap = false;
      }
      const lead = gap && line.pieces.length ? " " : "";
      const last = line.pieces[line.pieces.length - 1];
      if (last && last.parent === parent) last.text += lead + match[0];
      else line.pieces.push({ parent, text: lead + match[0] });
      gap = false;
    }
    if (end < node.data.length) gap = true;
  }
  return lines.length ? lines : null;
}

function span(className: string) {
  const element = document.createElement("span");
  element.className = className;
  return element;
}

/** The copy that plays the move: one block per measured line, placed exactly on the page's own line. */
function buildOverlay(element: HTMLElement, kind: "type" | "rise", lines: MeasuredLine[]) {
  const style = getComputedStyle(element);
  const overlay = span("intro-overlay");
  overlay.setAttribute("aria-hidden", "true");
  overlay.setAttribute("inert", "");
  overlay.dataset.kind = kind;
  overlay.style.setProperty("--intro-ink", style.color);
  overlay.style.setProperty("--intro-pad", `${Math.ceil(parseFloat(style.fontSize) * 0.35)}px`);
  if (style.textShadow && style.textShadow !== "none") overlay.style.textShadow = style.textShadow;
  const rows = lines.map((line) => {
    const row = span("intro-line");
    const text = span("intro-line-in");
    if (kind === "rise") {
      // The box a rising line comes out of: it cuts off what is below it.
      const mask = span("intro-win");
      mask.append(text);
      row.append(mask);
    } else row.append(text);
    for (const piece of line.pieces) {
      // The inline elements between the text and the tagged element (a link, emphasis), copied without their children.
      const chain: Element[] = [];
      for (let up: Element | null = piece.parent; up && up !== element; up = up.parentElement) chain.unshift(up);
      let host: HTMLElement = text;
      for (const original of chain) {
        const copy = original.cloneNode(false) as HTMLElement;
        for (const name of ["id", "data-intro", "data-intro-delay", "data-intro-run"]) copy.removeAttribute(name);
        host.append(copy);
        host = copy;
      }
      host.append(piece.text);
    }
    overlay.append(row);
    return { row, text, first: line.first };
  });
  element.append(overlay);
  element.setAttribute("data-intro-run", style.position === "static" ? "text" : "text-own");
  // Each block starts where the flow puts it; move it onto the page's own line, whatever the alignment or indent.
  const range = document.createRange();
  for (const line of rows) {
    const first = document.createTreeWalker(line.text, NodeFilter.SHOW_TEXT).nextNode() as Text | null;
    if (!first) continue;
    range.setStart(first, 0);
    range.setEnd(first, Math.min(1, first.data.length));
    const mine = range.getClientRects()[0];
    if (!mine) continue;
    line.row.style.left = `${line.first.left - mine.left}px`;
    line.row.style.top = `${line.first.top - mine.top}px`;
  }
  return { overlay, rows };
}

/** Sets a typed line up behind its windows and returns their animations, which start `start` ms after play().
 *
 *   row
 *     settled window > the line's text            the text up to where the edge was SETTLE_MS ago
 *     front window > hold > after window > hold   the part between that and the edge:
 *       two sheets of random letters, each in its character's place, shown in turn
 *
 * A window is a box as wide as the line that cuts off what overflows it and slides so its edge sits on a character boundary;
 * what it holds slides back by as much and so stays still on the page. */
function typedLine(row: HTMLElement, text: HTMLElement, start: number): { moves: Move[]; end: number } | null {
  const box = row.getBoundingClientRect();
  // The row, and so each window, is a whole number of pixels wide and a little wider than the text: an edge at `full` shows
  // the whole line, and every other edge is a whole pixel too, so the text stays sharp.
  const full = Math.ceil(box.width) + 1;
  row.style.width = `${full}px`;
  const range = document.createRange();
  const walker = document.createTreeWalker(text, NodeFilter.SHOW_TEXT);
  const cells: { char: string; left: number; right: number }[] = [];
  for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
    let at = 0;
    for (const char of node.data) {
      range.setStart(node, at);
      range.setEnd(node, at + char.length);
      at += char.length;
      const rect = range.getClientRects()[0];
      if (rect) cells.push({ char, left: rect.left - box.left, right: rect.right - box.left });
    }
  }
  const count = cells.length;
  if (!count) return null;

  const settled = span("intro-win");
  const front = span("intro-win is-front");
  const frontHold = span("intro-win-in");
  const after = span("intro-win is-after");
  const afterHold = span("intro-win-in");
  const sheets = [span("intro-roll"), span("intro-roll")];
  for (const sheet of sheets) {
    for (const cell of cells) {
      if (cell.char.trim() === "") continue;
      const letter = span("intro-cell");
      letter.textContent = scrambled(cell.char);
      letter.style.left = `${cell.left}px`;
      letter.style.width = `${cell.right - cell.left}px`;
      sheet.append(letter);
    }
    afterHold.append(sheet);
  }
  after.append(afterHold);
  frontHold.append(after);
  front.append(frontHold);
  settled.append(text);
  row.append(settled, front);

  // The edge after each step: nothing, then the right side of each character in turn.
  const edges = [0, ...cells.map((cell, index) => (index === count - 1 ? full : Math.round(cell.right)))];
  const steps = (value: (edge: number) => number): Keyframe[] =>
    edges.map((edge, index) => ({
      offset: index / count,
      transform: `translateX(${value(edge)}px)`,
      easing: index < count ? "steps(1, end)" : "linear",
    }));
  const duration = Math.min((count * 1000) / TYPE_CHARS_PER_S, LINE_MAX_MS);
  const at = (delay: number): KeyframeAnimationOptions => ({ duration, delay, fill: "both" });
  const turn = (shown: [number, number]): Keyframe[] => [
    { offset: 0, opacity: shown[0], easing: "steps(1, end)" },
    { offset: 0.5, opacity: shown[1], easing: "steps(1, end)" },
    { offset: 1, opacity: shown[1] },
  ];
  const flicker: KeyframeAnimationOptions = { duration: 2 * SCRAMBLE_TICK_MS, iterations: Infinity };
  return {
    moves: [
      { element: front, keyframes: steps((edge) => edge - full), options: at(start) },
      { element: frontHold, keyframes: steps((edge) => full - edge), options: at(start) },
      { element: settled, keyframes: steps((edge) => edge - full), options: at(start + SETTLE_MS) },
      { element: text, keyframes: steps((edge) => full - edge), options: at(start + SETTLE_MS) },
      { element: after, keyframes: steps((edge) => edge), options: at(start + SETTLE_MS) },
      { element: afterHold, keyframes: steps((edge) => -edge), options: at(start + SETTLE_MS) },
      { element: sheets[0], keyframes: turn([1, 0]), options: flicker },
      { element: sheets[1], keyframes: turn([0, 1]), options: flicker },
    ],
    end: start + duration + SETTLE_MS,
  };
}

/** Get every tagged element in the viewport ready, hidden in its starting state. Call it while the black covers the page, then
 * `play()` as the black lifts. Null when there is nothing to move or the visitor asked for reduced motion. */
export function prepareIntro(root: ParentNode = document): IntroRun | null {
  if (typeof window === "undefined" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return null;
  const overlays: HTMLElement[] = [];
  const marked: HTMLElement[] = [];
  const moves: Move[] = [];
  let typedLines = 0;
  let totalMs = 0;

  for (const element of Array.from(root.querySelectorAll<HTMLElement>("[data-intro]"))) {
    const kind = element.dataset.intro as Kind;
    if (kind !== "type" && kind !== "rise" && kind !== "fade") continue;
    if (element.hasAttribute("data-intro-run") || element.closest(".intro-overlay")) continue;
    const box = element.getBoundingClientRect();
    const onScreen = box.width > 0 && box.height > 0 && box.bottom > 0 && box.top < window.innerHeight && box.right > 0 && box.left < window.innerWidth;
    if (!onScreen) continue;
    const asked = Number(element.dataset.introDelay);
    const delay = element.dataset.introDelay !== undefined && Number.isFinite(asked) && asked >= 0 ? asked : null;
    const lines = kind === "fade" ? null : measureLines(element);
    if (!lines) {
      // A block, an image, or text that cannot be measured: the whole element fades up.
      element.setAttribute("data-intro-run", "fade");
      marked.push(element);
      const start = delay ?? FADE_DELAY_MS;
      moves.push({
        element,
        keyframes: [
          { opacity: 0, transform: `translateY(${FADE_SHIFT})` },
          { opacity: 1, transform: "translateY(0)" },
        ],
        options: { duration: FADE_MS, delay: start, easing: EASE_OUT_EXPO, fill: "both" },
      });
      totalMs = Math.max(totalMs, start + FADE_MS);
      continue;
    }
    const built = buildOverlay(element, kind as "type" | "rise", lines);
    overlays.push(built.overlay);
    marked.push(element);
    built.rows.forEach((line, index) => {
      if (kind === "rise") {
        const start = (delay ?? 0) + index * LINE_STAGGER_MS;
        moves.push({
          element: line.text,
          keyframes: [{ transform: "translateY(125%)" }, { transform: "translateY(0)" }],
          options: { duration: RISE_MS, delay: start, easing: EASE_OUT_EXPO, fill: "both" },
        });
        totalMs = Math.max(totalMs, start + RISE_MS);
        return;
      }
      const start = delay !== null ? delay + index * LINE_STAGGER_MS : TYPE_DELAY_MS + typedLines * LINE_STAGGER_MS;
      const typed = typedLine(line.row, line.text, start);
      if (!typed) return;
      moves.push(...typed.moves);
      typedLines += 1;
      totalMs = Math.max(totalMs, typed.end);
    });
    built.overlay.setAttribute("data-armed", "");
  }
  if (!marked.length) return null;

  const animations: Animation[] = [];
  let timer = 0;
  let finished = false;
  const width = window.innerWidth;
  // The copies were measured at this width; a change of width ends the moves rather than leaving them misplaced.
  const onResize = () => {
    if (window.innerWidth !== width) finish();
  };

  function finish() {
    if (finished) return;
    finished = true;
    window.clearTimeout(timer);
    window.removeEventListener("resize", onResize);
    for (const element of marked) element.removeAttribute("data-intro-run");
    for (const overlay of overlays) overlay.remove();
    for (const animation of animations) animation.cancel();
  }

  function play() {
    if (finished || animations.length) return;
    for (const move of moves) animations.push(move.element.animate(move.keyframes, move.options));
    window.addEventListener("resize", onResize);
    timer = window.setTimeout(finish, totalMs + 60);
  }

  return { play, finish, totalMs };
}
