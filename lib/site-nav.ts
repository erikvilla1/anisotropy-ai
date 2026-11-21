import { serviceHref, services } from "./services";
import { REPAIR_HREF, WING_HREF, WORKSPACE_ROOT, WORKSPACES } from "./workspaces";

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

/** Whether the Industries page is in the navigation. Off for now, at the lead's request of 2026-11-15 (ADR-0058 amendment
 * 8: "it feels too premature, hide for now"): no link in the header or the footer leads to it. The page itself stays at
 * its address, and `true` brings its links back. */
export const INDUSTRIES_IN_NAV: boolean = false;

/** Every page the navigation knows, in order: About, Services, Resources, Contact us (the lead's order of 2026-11-15,
 * ADR-0058 amendment 8; Resources stood before Services until then). The footer lists them all. */
export const siteNav: readonly NavItem[] = [
  { label: "About", href: "/about" },
  ...(INDUSTRIES_IN_NAV ? [{ label: "Industries", href: "/industries" }] : []),
  servicesNav,
  { label: "Resources", href: "/library" },
  { label: "Contact us", href: "/contact" },
];

/** Whether the header's Services item opens a panel of its five pages: the plus beside it, and under 1201 px the five links
 * under it in the folded menu. Off for now, at the lead's request of 2026-11-13 (ADR-0058 amendment 4): Services is a plain
 * link to its page. The pages, the footer's list and the panel's code stay, and `true` brings the panel back at every width. */
export const SERVICES_PANEL_IN_HEADER: boolean = false;

/** The header's items: the site's pages, Services without its children while its panel is hidden. */
export const primaryNav: readonly NavItem[] = siteNav.map((item) =>
  item.children && !SERVICES_PANEL_IN_HEADER ? { label: item.label, href: item.href } : item,
);

/** The old addresses that move to the workspace (ADR-0058 amendments 1 and 2), the same four as `MOVED_PAGES` in worker/routing.ts. */
export const MOVED_ADDRESSES: readonly string[] = ["/chat", "/chat/view", "/studio", "/studio/view"];

/** The workspace's own pages: the projects, one page per workspace, the wing's page of the FEA section (ADR-0118 amendment 1, in layout D
 * since ADR-0134) and the viewer a solved coupon opens in. */
const APP_PAGES: readonly string[] = [WORKSPACE_ROOT, ...WORKSPACES.map((w) => w.href), WING_HREF, REPAIR_HREF, `${REPAIR_HREF}/report`, `${WORKSPACE_ROOT}/fea/view`];

/** The app's addresses: the workspace's pages, and the four old addresses that move to it. They get the workspace's own header and no
 * footer. Any other path under `/workspace`, `/chat` or `/studio` is the 404 page, which keeps the site's header it was built with.
 * `/workspace/cad` is a section's page again (ADR-0124). */
export function isAppPath(pathname: string): boolean {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return APP_PAGES.includes(path) || MOVED_ADDRESSES.includes(path);
}

/** True where the workspace's header links back to the projects: a workspace page without a toolbar of its own, the viewer. The
 * workspaces' toolbars and the wing's and the repair's cards carry "All projects" already (components/workspace/shell.tsx, canvas-shell.tsx), and
 * `/workspace` is the projects. */
export function headerLinksToProjects(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "");
  return isAppPath(path) && path.startsWith(`${WORKSPACE_ROOT}/`) && path !== WING_HREF && path !== REPAIR_HREF && !WORKSPACES.some((w) => w.href === path);
}

/** The company's pages elsewhere, shown in the footer under the tagline (ADR-0077 amendment 60): LinkedIn and X, in that
 * order. `href` is the page's full address, as the lead gave them on 2026-11-14 (LinkedIn's is the company's page itself;
 * the address given led to its posts). An entry whose address is not filled in is not shown, so the footer never carries a
 * link that leads nowhere; `host` is where the address must lead. */
export type SocialLink = { label: string; host: string; href: string };
export const socialLinks: readonly SocialLink[] = [
  { label: "LinkedIn", host: "www.linkedin.com", href: "https://www.linkedin.com/company/anisotropy/" },
  { label: "X", host: "x.com", href: "https://x.com/anisotropy_ai" },
];
/** Whether an entry's address is a full https address on its own host. */
export const isSocialAddress = (link: SocialLink): boolean => link.href.startsWith(`https://${link.host}/`) && link.href.length > `https://${link.host}/`.length && !/\s/.test(link.href);
/** The entries the footer shows. */
export const shownSocialLinks = (links: readonly SocialLink[] = socialLinks): SocialLink[] => links.filter(isSocialAddress);

