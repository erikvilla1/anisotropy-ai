"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ArrowUp, ArrowUpRight, Menu, X } from "lucide-react";
import { primaryNav } from "@/lib/site-nav";
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

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  if (pathname === "/chat" || pathname.startsWith("/workspace"))
    return (
      <header className="site-header chat-site-header">
        <Wordmark />
        <Link className="text-button" href="/">
          Back to website <ArrowUpRight size={15} />
        </Link>
      </header>
    );
  // On the home page the header lies over the hero and scrolls away with it (ADR-0077); elsewhere it stays sticky.
  return (
    <header className={pathname === "/" ? "site-header is-home" : "site-header"}>
      <Wordmark onClick={close} />
      <nav
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
          Workspace <ArrowUpRight size={16} />
        </Link>
      </nav>
      <div className="header-actions">
        <span className="header-version">RESEARCH PREVIEW / V.01</span>
        <Link className="button header-cta" href="/workspace" onClick={close}>
          Workspace <ArrowUpRight size={16} />
        </Link>
        <button
          className="icon-button menu-toggle"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </button>
      </div>
    </header>
  );
}

/** The footer (ADR-0077 amendment 13), after PhysicsX's: the logo and the tagline in the left half, and the header's own
 * navigation (`lib/site-nav.ts`) as columns of links from the halfway line: the plain pages and the workspace in the first
 * column, then each item with children as a column of its own under its landing page. Under a rule, the copyright line, the
 * version and the way back to the top, on the same columns. Absent in the workspace, which is an app. */
export function SiteFooter() {
  const pathname = usePathname();
  if (pathname === "/chat" || pathname.startsWith("/workspace")) return null;
  const current = (href: string) => (pathname === href ? "page" : undefined);
  return (
    <footer className="site-footer">
      <div className="site-footer-top">
        <div className="site-footer-brand">
          <Wordmark />
          <p>Engineered from evidence.</p>
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
                Workspace <ArrowUpRight size={16} />
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
        <span>Research preview v.01</span>
        <a href="#">
          Back to top <ArrowUp size={16} />
        </a>
      </div>
    </footer>
  );
}
