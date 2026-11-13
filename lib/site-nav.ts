import { serviceHref, services } from "./services";
import { WORKSPACE_ROOT, WORKSPACES } from "./workspaces";

/** The header's items in the order of the audit of 2026-10-31 (ADR-0058). Calculator and Studio left the
 * header: the calculator lives on the home page and the studio is reached from the finite element page. The materials
 * library's link reads "Resources" (the lead's wording of 2026-11-13); the page it opens keeps its own title. */
export type NavItem = {
  label: string;
  href: string;
  children?: readonly { label: string; href: string }[];
};

export const primaryNav: readonly NavItem[] = [
  { label: "About", href: "/about" },
  { label: "Industries", href: "/industries" },
  { label: "Resources", href: "/library" },
  {
    label: "Services",
    href: "/services",
    children: services.map((service) => ({ label: service.title, href: serviceHref(service) })),
  },
  { label: "Contact us", href: "/contact" },
];

/** The old addresses that move to the workspace (ADR-0058 amendments 1 and 2), the same four as `MOVED_PAGES` in worker/routing.ts. */
export const MOVED_ADDRESSES: readonly string[] = ["/chat", "/chat/view", "/studio", "/studio/view"];

/** The workspace's own pages: the projects, one page per workspace, and the viewer a solved coupon opens in. */
const APP_PAGES: readonly string[] = [WORKSPACE_ROOT, ...WORKSPACES.map((w) => w.href), `${WORKSPACE_ROOT}/fea/view`];

/** The app's addresses: the workspace's pages, and the four old addresses that move to it. They get the workspace's own header and no
 * footer. Any other path under `/workspace`, `/chat` or `/studio` is the 404 page, which keeps the site's header it was built with;
 * `/workspace/cad` is one since its placeholder left (decision D5, ADR-0091 amendment 2). */
export function isAppPath(pathname: string): boolean {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return APP_PAGES.includes(path) || MOVED_ADDRESSES.includes(path);
}

/** True where the workspace's header links back to the projects: a workspace page without a toolbar of its own, the viewer. The
 * workspaces' toolbars carry "All projects" already (components/workspace/shell.tsx), and `/workspace` is the projects. */
export function headerLinksToProjects(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "");
  return isAppPath(path) && path.startsWith(`${WORKSPACE_ROOT}/`) && !WORKSPACES.some((w) => w.href === path);
}
