// What a page says in the browser's tab and in a link's preview (ADR-0058 amendment 2), and the shell's own rules: which addresses
// are the app's and where the workspace's header links back to the projects (ADR-0077 amendment 16). Read from the sources, since
// the pages import stylesheets that Node cannot load.
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import test from "node:test";
import { MOVED_ADDRESSES, headerLinksToProjects, isAppPath } from "../lib/site-nav";
import { bannedIn } from "../lib/studio-copy";
import { MOVED_PAGES } from "../worker/routing";

type Head = { file: string; route: string; title: string | null; description: string | null };

/** Every page, layout and not-found file under app/, with the title and description its `metadata` export writes. */
function heads(dir = "app"): Head[] {
  const out: Head[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...heads(path));
    else if (/^(page|layout|not-found)\.tsx$/.test(name)) {
      const source = readFileSync(path, "utf8").replace(/\r\n/g, "\n");
      const block = /export const metadata(?:: Metadata)? = \{([\s\S]*?)\n\};/.exec(source)?.[1] ?? null;
      const field = (key: string) => (block ? new RegExp(`\\n  ${key}:\\s*"([^"]*)"`).exec(`\n${block}`)?.[1] ?? null : null);
      const folder = relative("app", dir).split(sep).join("/");
      out.push({ file: relative(".", path).split(sep).join("/"), route: `/${folder}`.replace(/\/$/, "") || "/", title: field("title"), description: field("description") });
    }
  }
  return out;
}

const all = heads();
const page = (route: string) => all.find((h) => h.route === route && h.file.endsWith("/page.tsx"));

test("the root layout gives every title the site's name after a bar, and the home its tagline", () => {
  const layout = readFileSync("app/layout.tsx", "utf8");
  assert.match(layout, /title: \{ default: "Anisotropy \| Composites\. Calculated\.", template: "%s \| Anisotropy" \}/);
  assert.match(layout, /metadataBase: new URL\("https:\/\/anisotropy\.dev"\)/);
  assert.match(layout, /export const viewport: Viewport = \{ themeColor: "#0d0d0d" \}/);
  assert.ok(existsSync("app/favicon.ico"), "app/favicon.ico");
  assert.ok(existsSync("app/opengraph-image.jpg") && existsSync("app/opengraph-image.alt.txt"), "the shared image and its alt text");
});

test("every page's title is its bare name, which the template follows with the site's", () => {
  const titled = all.filter((h) => h.title !== null);
  assert.ok(titled.length >= 20, `${titled.length} titles read`);
  for (const h of titled) {
    assert.doesNotMatch(h.title!, /[|—]|Anisotropy\s*$/, `${h.file}: "${h.title}"`);
    assert.ok(h.title!.length > 0 && h.title!.length <= 40, `${h.file}: "${h.title}"`);
  }
  // a page with no title of its own takes its folder's layout's (the library's client page, from app/library/layout.tsx);
  // only the home falls back to the root's
  for (const h of all.filter((x) => x.file.endsWith("/page.tsx") && x.title === null)) {
    const layout = all.find((x) => x.file === h.file.replace(/page\.tsx$/, "layout.tsx"));
    assert.ok(h.route === "/" || Boolean(layout?.title), `${h.file} has no title of its own or in its folder's layout`);
  }
  assert.equal(all.find((h) => h.file === "app/not-found.tsx")?.title, "Page not found");
});

test("the workspace's titles and descriptions never name a tool, a vendor or the team, nor do the shell's (ADR-0091)", () => {
  const checked = all.filter((h) => isAppPath(h.route) || h.file === "app/layout.tsx" || h.file === "app/not-found.tsx");
  assert.ok(checked.length >= 10, `${checked.length} heads checked`);
  for (const h of checked) {
    assert.ok(h.file === "app/layout.tsx" || h.description, `${h.file} has a description`);
    assert.deepEqual(bannedIn(`${h.title ?? ""}\n${h.description ?? ""}`), [], h.file);
    // no screen layout, no machinery, no history of the site
    assert.doesNotMatch(h.description ?? "", /\b(on the left|in the centre|by its job|rows of the|moved under|workspace now)\b/i, h.file);
  }
  const root = readFileSync("app/layout.tsx", "utf8");
  assert.deepEqual(bannedIn(root.slice(root.indexOf("export const metadata"), root.indexOf("export default"))), []);
});

test("an old address carries the title and description of the page it goes to", () => {
  for (const [from, to] of [["/chat", "/workspace/fea"], ["/studio", "/workspace/fea"], ["/chat/view", "/workspace/fea/view"], ["/studio/view", "/workspace/fea/view"]]) {
    const old = page(from);
    const next = page(to);
    assert.ok(old && next, `${from} and ${to}`);
    assert.equal(old.title, next.title, from);
    assert.equal(old.description, next.description, from);
  }
});

test("the app's addresses get the workspace's header, and only the pages without a toolbar link back to the projects", () => {
  for (const path of ["/workspace", "/workspace/fea", "/workspace/laminate", "/workspace/fea/view", "/chat", "/chat/view", "/studio", "/studio/view"])
    assert.ok(isAppPath(path), path);
  for (const path of ["/", "/about", "/library", "/services/finite-element-modeling", "/_not-found", "/chatroom", "/studios"])
    assert.ok(!isAppPath(path), path);
  // an unknown address under an old one is the 404 page, built with the site's header: the browser must draw the same header
  for (const path of ["/studio/x", "/chat/anything", "/studio/view/more"]) assert.ok(!isAppPath(path), path);
  // so is one under the workspace, among them the CAD placeholder's, gone with decision D5 (ADR-0091 amendment 2)
  for (const path of ["/workspace/cad", "/workspace/cad/", "/workspace/x", "/workspace/fea/x"]) assert.ok(!isAppPath(path), path);
  assert.ok(isAppPath("/studio/view/") && isAppPath("/chat/"), "a trailing slash");
  assert.deepEqual([...MOVED_ADDRESSES].sort(), Object.keys(MOVED_PAGES).sort(), "the shell's old addresses are the Worker's");
  for (const path of ["/workspace/fea/view", "/workspace/fea/view/"]) assert.ok(headerLinksToProjects(path), path);
  for (const path of ["/workspace", "/workspace/", "/workspace/fea", "/workspace/laminate", "/workspace/cad", "/chat", "/about"]) assert.ok(!headerLinksToProjects(path), path);
});

test("↗ marks only a link that opens a new tab and says so, in the shell, the library's property table and a job's files", () => {
  // the files this rule has reached (ADR-0077 amendment 16); the pages' own links follow in their fix groups
  const files = ["components/site-shell.tsx", "components/property-table.tsx", "components/studio/job-files.tsx"];
  let links = 0;
  for (const file of files) {
    const source = readFileSync(file, "utf8");
    for (const m of source.matchAll(/<(Link|a)\s((?:[^>{]|\{[^}]*\})*)>([\s\S]*?)<\/\1>/g)) {
      const [, , attributes, content] = m;
      links += 1;
      if (!/↗|ArrowUpRight|ExternalLink|MoveUpRight/.test(content)) continue;
      assert.match(attributes, /target="_blank"/, `${file}: ${m[0].slice(0, 120)}`);
      assert.match(`${attributes} ${content}`, /new (tab|window)/, `${file} announces the new tab: ${m[0].slice(0, 120)}`);
    }
  }
  assert.ok(links >= 8, `${links} links read`);
  assert.doesNotMatch(readFileSync("components/site-shell.tsx", "utf8"), /ArrowUpRight|ExternalLink|MoveUpRight/);
});
