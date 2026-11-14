"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type MouseEvent, type RefObject } from "react";
import { ArrowLeft, ArrowRight, ArrowUp, Menu, X } from "lucide-react";
import { headerLinksToProjects, isAppPath, primaryNav, siteNav } from "@/lib/site-nav";
import { AT_TOP, headerAfterFocus, headerAfterLock, headerAfterScroll, type HeaderMemory, type HeaderPage } from "@/components/header-scroll";
import { ServicesMenu } from "@/components/services-menu";

/** The logo (ADR-0080): the triangle, then the name, both drawn by `app/brand.css` from the vector files in
 * `public/assets/brand/`. The word itself stays in the link, hidden from view, for screen readers and search engines. */
function Wordmark({ onClick }: { onClick?: () => void }) {
  return (
    <Link className="wordmark" href="/" aria-label="Anisotropy home" onClick={onClick}>
      <span className="brand-mark" aria-hidden="true" />
      <span className="brand-name">Anisotropy</span>
    </Link>
  );
}

const MENU_ID = "site-menu";

/** The site header on scroll: it leaves as the page goes down and comes back, as a bar fixed to the window's top, as soon as
 * the page goes up (the rule is components/header-scroll.ts; app/globals.css draws it). This reads the page at every scroll,
 * whenever the focus comes into the header and whenever a stage locks the page, and writes the answer on the header as
 * `data-scroll`: nothing at the page's top, "away" or "hidden" while it is out of sight above the window, "shown" while it
 * is the bar. It is written straight on the element, not through React's state, so the header changes in the frame the
 * page scrolled in. */
function useHeaderScroll(header: RefObject<HTMLElement | null>, active: boolean) {
  useEffect(() => {
    const element = header.current;
    if (!active || !element) return;
    const root = document.documentElement;
    let memory: HeaderMemory = AT_TOP;
    // The page as the rule sees it. Each part is read only when the rule asks for it, and on most scrolls it asks for little.
    const page: HeaderPage = {
      // Past its foot a phone's page springs back up, and that is not a scroll up: the page counts as at its foot.
      get y() {
        return Math.min(window.scrollY, root.scrollHeight - root.clientHeight);
      },
      get height() {
        return element.offsetHeight;
      },
      // The folded navigation's button and the Services panel's each say when they are open. One that is not drawn does
      // not count: the folded navigation's stays as it was when the window grows wide.
      get expanded() {
        return [...element.querySelectorAll('[aria-expanded="true"]')].some((control) => control.getClientRects().length > 0);
      },
      get focused() {
        return element.querySelector(":focus-visible") !== null;
      },
      // A stage that takes the scroll over (components/home/tour-driver.ts) locks the page while a step plays on it and
      // for a moment after the page was stopped there. No page mounts one now: the home page's demo follows the scroll.
      get scripted() {
        return root.hasAttribute("data-tour-lock");
      },
    };
    const write = (next: HeaderMemory) => {
      const before = memory.state;
      memory = next;
      if (next.state === before) return;
      if (next.state === "top") {
        delete element.dataset.scroll;
        return;
      }
      // Straight from the page's flow to the bar: it is first put above the window, and the browser is made to take note,
      // so that it slides in from there.
      if (before === "top" && next.state === "shown") {
        element.dataset.scroll = "away";
        void element.offsetHeight;
      }
      element.dataset.scroll = next.state;
    };
    const onScroll = () => write(headerAfterScroll(memory, page));
    const onFocus = () => write(headerAfterFocus(memory, page));
    // That lock goes on without a scroll, and on a stage that holds the window a gesture plays a step and scrolls nothing.
    const lock = new MutationObserver(() => {
      if (root.hasAttribute("data-tour-lock")) write(headerAfterLock(memory, page));
    });
    onScroll(); // a page that opens already scrolled, as a reload does
    window.addEventListener("scroll", onScroll, { passive: true });
    element.addEventListener("focusin", onFocus);
    lock.observe(root, { attributes: true, attributeFilter: ["data-tour-lock"] });
    return () => {
      window.removeEventListener("scroll", onScroll);
      element.removeEventListener("focusin", onFocus);
      lock.disconnect();
      delete element.dataset.scroll;
    };
  }, [header, active]);
}

/** The header. On narrow screens the links fold into a menu (ADR-0077 amendment 16): its button comes before it, so the next Tab
 * after opening reaches the links; opening moves the focus to the first link, Escape closes it and returns to the button, and a
 * press outside the header, the focus leaving it or a change of page closes it. Arrows: → for Workspace, ← for the workspace
 * header's ways back; ↗ is kept for a link that opens a new tab. */
export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const header = useRef<HTMLElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLElement>(null);
  const close = () => setOpen(false);
  const app = isAppPath(pathname);

  // The workspace's header is another one, and stays where it is.
  useHeaderScroll(header, !app);
  useEffect(() => {
    setOpen(false);
  }, [pathname]);
  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLElement>("a")?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      toggle.current?.focus();
    }
    // A press outside the header, or Tab past the menu's last link into the page, closes it.
    function onOutside(event: Event) {
      if (!header.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onOutside);
    document.addEventListener("focusin", onOutside);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onOutside);
      document.removeEventListener("focusin", onOutside);
    };
  }, [open]);

  if (app)
    return (
      <header className="site-header chat-site-header">
        <Wordmark />
        <div className="chat-site-links">
          {headerLinksToProjects(pathname) ? (
            <Link className="text-button is-projects" href="/workspace">
              <ArrowLeft size={15} /> All projects
            </Link>
          ) : null}
          <Link className="text-button is-website" href="/">
            <ArrowLeft size={15} /> Back to website
          </Link>
        </div>
      </header>
    );
  // At a page's top the header is in the page's flow and scrolls away with it; on the home page it lies over the hero
  // (ADR-0077). Further down it comes back as a bar at the window's top when the page scrolls up (useHeaderScroll).
  return (
    <header ref={header} className={pathname === "/" ? "site-header is-home" : "site-header"}>
      <Wordmark onClick={close} />
      <button
        ref={toggle}
        type="button"
        className="icon-button menu-toggle"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls={MENU_ID}
        onClick={() => setOpen(!open)}
      >
        {open ? <X /> : <Menu />}
      </button>
      <nav
        id={MENU_ID}
        ref={menu}
        className={`main-nav ${open ? "open" : ""}`}
        aria-label="Main navigation"
      >
        {primaryNav.map((item) =>
          item.children ? (
            <ServicesMenu key={item.href} item={item} expanded={open} onNavigate={close} />
          ) : (
            <Link
              href={item.href}
              key={item.href}
              // On a page under the link's own, such as a service's, the link marks the section, as the Services panel's link does.
              aria-current={pathname === item.href ? "page" : pathname.startsWith(`${item.href}/`) ? "true" : undefined}
              onClick={close}
            >
              {item.label}
            </Link>
          ),
        )}
        <Link className="mobile-chat-cta" href="/workspace" onClick={close}>
          Workspace <ArrowRight size={16} />
        </Link>
      </nav>
      <div className="header-actions">
        <Link className="button header-cta" href="/workspace" onClick={close}>
          Workspace <ArrowRight size={16} />
        </Link>
      </div>
    </header>
  );
}

/** Back to top: the page scrolls to the top and the focus goes with it, to the logo, so the next Tab continues from the header.
 * Without a script the link still goes to the page's content. */
function backToTop(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  window.scrollTo({ top: 0 });
  document.querySelector<HTMLElement>(".site-header .wordmark")?.focus({ preventScroll: true });
}

/** The footer (ADR-0077 amendment 13), after PhysicsX's: the logo and the tagline in the left half, and the site's
 * navigation (`siteNav` in `lib/site-nav.ts`, Services with its five pages, also while the header hides its panel) as columns of links from the halfway line: the plain pages and the workspace in the first
 * column, then each item with children as a column of its own under its landing page. Under a rule, the copyright line, the
 * release stage and the way back to the top, on the same columns. Absent in the workspace, which is an app. The tagline and the
 * stage are the founder's choice of 2026-11-12 (ADR-0077 amendment 16). */
export function SiteFooter() {
  const pathname = usePathname();
  if (isAppPath(pathname)) return null;
  const current = (href: string) => (pathname === href ? "page" : undefined);
  return (
    <footer className="site-footer">
      <div className="site-footer-top">
        <div className="site-footer-brand">
          <Wordmark />
          <p>Composites. Calculated.</p>
        </div>
        <nav className="site-footer-nav" aria-label="Footer">
          <ul>
            {siteNav
              .filter((item) => !item.children)
              .map((item) => (
                <li key={item.href}>
                  <Link href={item.href} aria-current={current(item.href)}>
                    {item.label}
                  </Link>
                </li>
              ))}
            <li>
              <Link href="/workspace">
                Workspace <ArrowRight size={16} />
              </Link>
            </li>
          </ul>
          {siteNav
            .filter((item) => item.children)
            .map((item) => (
              <ul key={item.href}>
                <li>
                  <Link href={item.href} aria-current={current(item.href)}>
                    {item.label}
                  </Link>
                </li>
                {item.children?.map((child) => (
                  <li key={child.href} className="site-footer-child">
                    <Link href={child.href} aria-current={current(child.href)}>
                      {child.label}
                    </Link>
                  </li>
                ))}
              </ul>
            ))}
        </nav>
      </div>
      <div className="site-footer-bottom">
        <span>© {new Date().getFullYear()} Anisotropy</span>
        <span>Closed beta</span>
        <a href="#main" onClick={backToTop}>
          Back to top <ArrowUp size={16} />
        </a>
      </div>
    </footer>
  );
}
