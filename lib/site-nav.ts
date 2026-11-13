import { serviceHref, services } from "./services";
import { WORKSPACE_ROOT, WORKSPACES } from "./workspaces";

/** The site's pages in the order of the audit of 2026-10-31 (ADR-0058). Calculator and Studio left the navigation: the
 * calculator has its own page and the studio is reached from the finite element page. The materials library's link reads
 * "Resources" (the lead's wording of 2026-11-13); the page it opens keeps its own title. */
export type NavItem = {
  label: string;
  href: string;
  children?: readonly { label: string; href: string }[];
};

/** Services and its five pages: a column in the footer, and in the header a button that opens a panel (components/services-menu.tsx). */
export const servicesNav: NavItem = {
  label: "Services",
  href: "/services",
  children: services.map((service) => ({ label: service.title, href: serviceHref(service) })),
};

/** Every page the navigation knows, in order. The footer lists them all. */
export const siteNav: readonly NavItem[] = [
  { label: "About", href: "/about" },
  { label: "Industries", href: "/industries" },
  { label: "Resources", href: "/library" },
  servicesNav,
  { label: "Contact us", href: "/contact" },
];

/** Whether the header shows Services and its panel. Off for now, at the lead's request of 2026-11-13 (ADR-0058 amendment 4):
 * the pages, the footer's list and the panel's code stay, and `true` brings the item back at every width. */
export const SERVICES_IN_HEADER: boolean = false;

/** The header's items: the site's pages, without Services while it is hidden. */
export const primaryNav: readonly NavItem[] = siteNav.filter((item) => SERVICES_IN_HEADER || item !== servicesNav);

/** The old addresses that move to the workspace (ADR-0058 amendments 1 and 2), the same four as `MOVED_PAGES` in worker/routing.ts. */
export const MOVED_ADDRESSES: readonly string[] = ["/chat", "/chat/view", "/studio", "/studio/view"];

/** The app's addresses: the workspace, and the four old addresses that move to it. They get the workspace's own header and no
 * footer. Any other path under `/chat` or `/studio` is the 404 page, which keeps the site's header it was built with. */
export function isAppPath(pathname: string): boolean {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return path === "/workspace" || path.startsWith("/workspace/") || MOVED_ADDRESSES.includes(path);
}

/** True where the workspace's header links back to the projects: a workspace page without a toolbar of its own (CAD, the viewer).
 * The built workspaces' toolbars carry "All projects" already (components/workspace/shell.tsx), and `/workspace` is the projects. */
export function headerLinksToProjects(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "");
  return path.startsWith(`${WORKSPACE_ROOT}/`) && !WORKSPACES.some((w) => w.status === "built" && w.href === path);
}
