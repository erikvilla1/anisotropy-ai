"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  if (pathname === "/chat")
    return (
      <header className="site-header chat-site-header">
        <Link className="wordmark" href="/" aria-label="Anisotropy AI home">
          <img
            className="brand-symbol"
            src="/assets/brand/anisotropy-mark.svg"
            alt=""
            width="40"
            height="40"
          />
          <span>
            Anisotropy<span className="wordmark-ai">AI</span>
          </span>
        </Link>
        <Link className="text-button" href="/">
          Back to website <ArrowUpRight size={15} />
        </Link>
      </header>
    );
  return (
    <header className="site-header">
      <Link
        className="wordmark"
        href="/"
        aria-label="Anisotropy AI home"
        onClick={() => setOpen(false)}
      >
        <img
          className="brand-symbol"
          src="/assets/brand/anisotropy-mark.svg"
          alt=""
          width="40"
          height="40"
        />
        <span>
          Anisotropy<span className="wordmark-ai">AI</span>
        </span>
      </Link>
      <nav
        className={`main-nav ${open ? "open" : ""}`}
        aria-label="Main navigation"
      >
        {[
          ["About", "/about"],
          ["Industries", "/industries"],
          ["Services", "/services"],
          ["Materials library", "/library"],
        ].map(([label, href]) => (
          <Link
            href={href}
            key={href}
            aria-current={pathname === href ? "page" : undefined}
            onClick={() => setOpen(false)}
          >
            {label}
          </Link>
        ))}
        <Link
          className="mobile-chat-cta"
          href="/chat"
          onClick={() => setOpen(false)}
        >
          Open chat <ArrowUpRight size={16} />
        </Link>
      </nav>
      <div className="header-actions">
        <span className="header-version">RESEARCH PREVIEW / V.01</span>
        <Link
          className="button header-cta"
          href="/chat"
          onClick={() => setOpen(false)}
        >
          Open chat <ArrowUpRight size={16} />
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
  if (pathname === "/chat") return null;
  return (
    <footer className="site-footer">
      <Link className="wordmark" href="/" aria-label="Anisotropy AI home">
        <img
          className="brand-symbol"
          src="/assets/brand/anisotropy-mark.svg"
          alt=""
          width="40"
          height="40"
        />
        <span>
          Anisotropy<span className="wordmark-ai">AI</span>
        </span>
      </Link>
      <span>Engineered from evidence.</span>
      <span>
        © {new Date().getFullYear()} Anisotropy AI{" "}
        <span className="footer-divider">/</span> Research preview v.01
      </span>
      <a href="#">
        Back to top <ArrowUpRight size={14} />
      </a>
    </footer>
  );
}
