"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { primaryNav } from "@/lib/site-nav";
import { ServicesMenu } from "@/components/services-menu";

function Wordmark({ onClick }: { onClick?: () => void }) {
  return (
    <Link className="wordmark" href="/" aria-label="Anisotropy home" onClick={onClick}>
      <img
        className="brand-symbol"
        src="/assets/brand/anisotropy-mark.svg"
        alt=""
        width="40"
        height="40"
      />
      <span>Anisotropy</span>
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

export function SiteFooter() {
  const pathname = usePathname();
  if (pathname === "/chat" || pathname.startsWith("/workspace")) return null;
  return (
    <footer className="site-footer">
      <Wordmark />
      <span>Engineered from evidence.</span>
      <span>
        © {new Date().getFullYear()} Anisotropy{" "}
        <span className="footer-divider">/</span> Research preview v.01
      </span>
      <a href="#">
        Back to top <ArrowUpRight size={14} />
      </a>
    </footer>
  );
}
