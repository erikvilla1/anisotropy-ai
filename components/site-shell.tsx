"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { ArrowLeft, ArrowRight, ArrowUp, Menu, X } from "lucide-react";
import { headerLinksToProjects, isAppPath, primaryNav } from "@/lib/site-nav";
import { ServicesMenu } from "@/components/services-menu";

/** The logo (ADR-0080): the triangle, then the name, both drawn by `app/brand.css` from the vector files in
 * `public/assets/brand/`. The word itself stays in the link, hidden from view, for screen readers and search engines. */
function Wordmark({ onClick }: { onClick?: () => void }) {
  return (
    <Link className="wordmark" href="/" aria-label="Anisotropy home" onClick={onClick}>
      <span className="brand-mark" aria-hidden="true" />
      <span className="brand-name" aria-hidden="true" />
      <span className="brand-text">Anisotropy</span>
    </Link>
  );
}

const MENU_ID = "site-menu";

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

  if (isAppPath(pathname))
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
  // On the home page the header lies over the hero and scrolls away with it (ADR-0077); elsewhere it stays sticky.
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
              aria-current={pathname === item.href ? "page" : undefined}
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

/** The footer (ADR-0077 amendment 13), after PhysicsX's: the logo and the tagline in the left half, and the header's own
 * navigation (`lib/site-nav.ts`) as columns of links from the halfway line: the plain pages and the workspace in the first
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
            {primaryNav
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
          {primaryNav
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
