import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { CouponVisual } from "../components/coupon-visual";
import { keepPlaying } from "../components/home/hero-video-keeper";
import { MediaSlot } from "../components/media-slot";
import { comingTests, listed, roadmap, validationGate } from "../lib/about-content";
import { bannedIn } from "../lib/studio-copy";

// The marketing pages (home, About, Industries, Contact, Services and its five pages) as the audit of 2026-11-12 left them: no
// empty picture slot, no internal tool, record or old product name in the words a visitor reads, and the ↗ arrow only on a
// link that opens a new tab.

const servicePages = readdirSync(join("app", "services"), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => join("app", "services", entry.name, "page.tsx"));
const MARKETING_FILES = [
  "app/page.tsx",
  "app/about/page.tsx",
  "app/industries/page.tsx",
  "app/contact/page.tsx",
  "app/services/page.tsx",
  ...servicePages,
  "components/services/service-page.tsx",
  "components/closing-band.tsx",
  "components/coupon-visual.tsx",
  "components/media-slot.tsx",
  // The home page's product demo (ADR-0095); the calculator and its tour are unmounted from the page but kept, so their words are
  // held to the same rules.
  "components/home/product-demo.tsx",
  "components/home/product-demo-copy.ts",
  "components/home/demo-tour.tsx",
  "components/home/laminate-hero.tsx",
  "components/home/laminate-panels.tsx",
  "components/home/scroll-to-explore.tsx",
  "components/home/hero-video-keeper.tsx",
  "lib/services.ts",
  "lib/about-content.ts",
  "lib/team.ts",
];

/** Attributes whose values are addresses, classes or settings, not words a visitor reads. */
const CODE_ATTRIBUTES = new Set(["className", "href", "src", "id", "key", "type", "rel", "target", "role", "poster", "ratio", "kind", "mode", "sizes", "webpSrcSet", "media", "preload", "htmlFor", "inputMode", "autoComplete", "style"]);

function parse(file: string): ts.SourceFile {
  return ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
}

/** Every piece of text in a source file that can reach the page: string literals, template text and JSX text, without module
 * names, the values of code attributes, a data attribute's name set through an object, a type, a value compared with, or
 * comments. */
function wordsOf(file: string): string[] {
  const words: string[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return;
    if (ts.isJsxAttribute(node)) {
      const name = node.name.getText();
      if (CODE_ATTRIBUTES.has(name) || name.startsWith("data-")) return;
    }
    // `{ "data-run-id": … }` spread onto an element names an attribute, as `data-run-id=` does in JSX; its value is still read.
    if (ts.isStringLiteral(node) && ts.isPropertyAssignment(node.parent) && node.parent.name === node && node.text.startsWith("data-")) return;
    // A string in a type (`TourView["engine"]`) or compared with (`id === "engine"`) is a key in the code, not a word on the page.
    if (ts.isLiteralTypeNode(node)) return;
    if (ts.isStringLiteral(node) && ts.isBinaryExpression(node.parent)
      && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(node.parent.operatorToken.kind)) return;
    if (ts.isCallExpression(node) && /(querySelector|getElementById|matchMedia|addEventListener|removeEventListener)$/.test(node.expression.getText())) return;
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) words.push(node.text);
    else if (ts.isTemplateExpression(node)) words.push(node.head.text, ...node.templateSpans.map((span) => span.literal.text));
    else if (ts.isJsxText(node) && node.text.trim()) words.push(node.text.trim());
    ts.forEachChild(node, visit);
  };
  visit(parse(file));
  return words;
}

test("an empty media slot renders nothing, a picture keeps its space, and a clip can be paused and never plays for reduced motion", () => {
  assert.equal(renderToStaticMarkup(createElement(MediaSlot, { label: "A coupon in the tensile frame" })), "");
  assert.equal(renderToStaticMarkup(createElement(MediaSlot, { label: "A coupon", kind: "clip" })), "");
  const picture = renderToStaticMarkup(createElement(MediaSlot, {
    label: "Microscopy", src: "/assets/images/microscopy.jpg", alt: "Microscopy image", width: 2880, height: 2160,
    webpSrcSet: "/assets/images/microscopy-800.webp 800w", sizes: "50vw",
  }));
  assert.match(picture, /<picture><source type="image\/webp" srcSet="\/assets\/images\/microscopy-800.webp 800w" sizes="50vw"\/><img src="\/assets\/images\/microscopy.jpg" width="2880" height="2160"/);
  assert.doesNotMatch(picture, /SLOT/);
  const clip = renderToStaticMarkup(createElement(MediaSlot, { label: "A layup", kind: "clip", src: "/assets/clips/layup.mp4" }));
  assert.match(clip, /<video[^>]* controls=""/);
  assert.match(clip, /<source src="\/assets\/clips\/layup.mp4" media="\(prefers-reduced-motion: no-preference\)"\/>/);
});

test("the marketing pages name no internal tool, record or old product name, and Abaqus only as the input file they export", () => {
  for (const file of MARKETING_FILES) {
    for (const text of wordsOf(file)) {
      // Erik's decision D18 of 2026-11-12: the site says "Abaqus input file (.inp)" and never names the reference solver.
      const shown = text.replace(/Abaqus input file \(\.inp\)/g, "");
      assert.deepEqual(bannedIn(shown), [], `${file}: "${text}"`);
      assert.doesNotMatch(text, /\bthe studio\b|\bstudio (session|job)s?\b|\bthe chat\b|\bengine says\b|\bthe engine'?s?\b|\bour (kernel|engine)\b/i, `${file}: "${text}"`);
      assert.doesNotMatch(text, /IMAGE SLOT|CLIP SLOT|github\.com|\/v1\/|ncamp-|\bdecks?\b/i, `${file}: "${text}"`);
      // Erik's decision D4 of 2026-11-12: a customer gets the report and the Abaqus input file; the full package stays in the
      // developer view, so no page offers it, the reference solver's input or a run record.
      assert.doesNotMatch(text, /\bfull package\b|\breference solver inputs?\b|\bsolver inputs\b|\brun record\b/i, `${file}: "${text}"`);
    }
  }
});

test("the north-east arrow is kept for links that open a new tab; links on the site point right", () => {
  for (const file of MARKETING_FILES.filter((name) => name.endsWith(".tsx"))) {
    const source = parse(file);
    const visit = (node: ts.Node) => {
      if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) && /^(ArrowUpRight|MoveUpRight)$/.test(node.tagName.getText())) {
        let parent: ts.Node | undefined = node.parent;
        while (parent && !(ts.isJsxElement(parent) && /^(a|Link)$/.test(parent.openingElement.tagName.getText()))) parent = parent.parent;
        const opens = parent && ts.isJsxElement(parent)
          ? parent.openingElement.attributes.properties.some((attribute) => ts.isJsxAttribute(attribute) && attribute.name.getText() === "target" && attribute.initializer?.getText() === '"_blank"')
          : false;
        assert.ok(opens, `${file}: ${node.tagName.getText()} outside a link that opens a new tab, at ${source.getLineAndCharacterOfPosition(node.getStart()).line + 1}`);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
});

test("The Basement is named in words, and its mark is shown nowhere until written permission is recorded (ADR-0081 amendment 2)", () => {
  const sources = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sources(path);
    return /\.(tsx?|css)$/.test(entry.name) ? [path] : [];
  });
  for (const file of ["app", "components", "lib"].flatMap(sources))
    assert.doesNotMatch(readFileSync(file, "utf8"), /uc-san-diego-the-basement/, file);
  assert.equal(existsSync(join("public", "assets", "partners", "uc-san-diego-the-basement-white.png")), false);
  assert.match(readFileSync("app/page.tsx", "utf8"), /The Basement, UC San Diego/);
});

test("a page title's line breaks keep a space before them, since a phone hides the breaks (app/inner-pages.css)", () => {
  // JSX drops the space before a line end, so a title written "Engineering built" + newline + <br /> would read "builton" once
  // the <br /> is hidden; each break needs a {" "} before it.
  let breaks = 0;
  for (const file of ["app/about/page.tsx", "app/contact/page.tsx", "app/industries/page.tsx", "app/services/page.tsx", ...servicePages]) {
    const source = parse(file);
    const inTitle = (node: ts.Node): boolean => {
      for (let up: ts.Node | undefined = node.parent; up; up = up.parent) {
        if (ts.isJsxAttribute(up) && up.name.getText() === "headline") return true;
        if (ts.isJsxElement(up) && up.openingElement.attributes.properties.some((attribute) =>
          ts.isJsxAttribute(attribute) && attribute.name.getText() === "className" && attribute.initializer?.getText() === '"page-opening-title"')) return true;
      }
      return false;
    };
    const visit = (node: ts.Node) => {
      if (ts.isJsxSelfClosingElement(node) && node.tagName.getText() === "br" && inTitle(node)) {
        const siblings = (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent) ? [...node.parent.children] : [])
          .filter((child) => !(ts.isJsxText(child) && child.containsOnlyTriviaWhiteSpaces));
        const before = siblings[siblings.indexOf(node) - 1];
        const spaced = before !== undefined && ts.isJsxExpression(before) && before.expression !== undefined
          && ts.isStringLiteral(before.expression) && /\s$/.test(before.expression.text);
        assert.ok(spaced, `${file}: a title's <br /> without a space before it, at ${source.getLineAndCharacterOfPosition(node.getStart()).line + 1}`);
        breaks += 1;
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  assert.equal(breaks, 4 + servicePages.length);
});

test("the coupon illustration carries no words of its own, which would shrink with it", () => {
  for (const mode of ["geometry", "stress", "failure"] as const) {
    const svg = renderToStaticMarkup(createElement(CouponVisual, { mode }));
    assert.doesNotMatch(svg, /<text/, mode);
    assert.match(svg, /aria-label="Illustration of the ASTM D3039 tension strip with bonded tabs/);
  }
});

test("About and the finite element page list the tests to come once, and the roadmap says what is next as a milestone", () => {
  assert.equal(listed(["a", "b", "c"]), "a, b, and c");
  assert.equal(listed(["a", "b"]), "a and b");
  assert.ok(roadmap[0].text.includes(listed(comingTests)));
  assert.match(validationGate, /^Next milestone:/);
  for (const stage of roadmap) assert.doesNotMatch(stage.title, /&/);
  assert.match(readFileSync("app/services/finite-element-modeling/page.tsx", "utf8"), /roadmap\.slice\(2\)/);
});

test("a hero clip the visitor paused is never resumed by the keeper", async () => {
  // The keeper tries at most once a second, counted from the clock's start, so the test waits for the clock's first second.
  while (performance.now() < 1100) await new Promise((resolve) => setTimeout(resolve, 50));
  const handlers: Record<string, () => void> = {};
  let plays = 0;
  const video = {
    currentSrc: "/media/hero.mp4", paused: true, currentTime: 3,
    play: () => { plays += 1; return Promise.resolve(); },
    addEventListener: (type: string, handler: () => void) => { handlers[type] = handler; },
    removeEventListener: () => {},
  } as unknown as HTMLVideoElement;
  const page = globalThis as unknown as { document?: unknown };
  const before = page.document;
  page.document = { visibilityState: "visible", addEventListener: () => {}, removeEventListener: () => {} };
  try {
    let held = true;
    const stop = keepPlaying(video, () => held);
    handlers.pause();
    handlers.ended();
    assert.equal(plays, 0);
    held = false;
    handlers.pause();
    assert.equal(plays, 1);
    stop();
  } finally {
    page.document = before;
  }
});
