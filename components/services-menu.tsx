"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent } from "react";
import { ChevronDown } from "lucide-react";
import type { NavItem } from "@/lib/site-nav";

const LIST_ID = "services-menu";
const CLOSE_DELAY_MS = 150;

/** The Services item of the header: a link to the landing page plus a disclosure listing the five service pages.
 * Disclosure pattern (a button with aria-expanded and a plain list), not a menu role, so every entry stays an
 * ordinary link. On narrow screens the stylesheet shows the list inside the open mobile navigation and hides the button. */
export function ServicesMenu({ item, expanded, onNavigate }: {
  item: NavItem;
  /** True while the mobile navigation is open: the list then renders in place without the disclosure. */
  expanded: boolean;
  onNavigate: () => void;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const focusIndex = useRef<number | null>(null);
  const closeTimer = useRef<number | null>(null);
  const children = item.children ?? [];

  useEffect(() => {
    setOpen(false);
  }, [pathname]);
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);
  useEffect(() => {
    if (!open || focusIndex.current === null) return;
    links()[focusIndex.current]?.focus();
    focusIndex.current = null;
  }, [open]);
  useEffect(
    () => () => {
      if (closeTimer.current) window.clearTimeout(closeTimer.current);
    },
    [],
  );

  function links(): HTMLAnchorElement[] {
    return Array.from(root.current?.querySelectorAll<HTMLAnchorElement>(`#${LIST_ID} a`) ?? []);
  }
  function openAndFocus(index: number) {
    focusIndex.current = index;
    if (open) {
      links()[index]?.focus();
      focusIndex.current = null;
    } else setOpen(true);
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const all = links();
    const current = all.indexOf(document.activeElement as HTMLAnchorElement);
    if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
      button.current?.focus();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      openAndFocus(current < 0 ? 0 : Math.min(current + 1, all.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (current <= 0) {
        setOpen(false);
        button.current?.focus();
      } else all[current - 1]?.focus();
    }
  }
  function onBlur(event: FocusEvent<HTMLDivElement>) {
    if (!root.current?.contains(event.relatedTarget as Node)) setOpen(false);
  }
  function hoverOpen() {
    if (!window.matchMedia("(hover: hover)").matches) return;
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    setOpen(true);
  }
  function hoverClose() {
    if (!window.matchMedia("(hover: hover)").matches) return;
    closeTimer.current = window.setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  }
  const current = pathname === item.href || pathname.startsWith(`${item.href}/`);
  return (
    <div
      className={`nav-disclosure ${open ? "open" : ""}`}
      ref={root}
      onKeyDown={onKeyDown}
      onBlur={onBlur}
      onPointerEnter={hoverOpen}
      onPointerLeave={hoverClose}
    >
      <Link href={item.href} aria-current={current ? "page" : undefined} onClick={onNavigate}>
        {item.label}
      </Link>
      <button
        type="button"
        className="nav-disclosure-button"
        ref={button}
        aria-expanded={open}
        aria-controls={LIST_ID}
        aria-label="Show services"
        onClick={() => setOpen(!open)}
      >
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      <ul id={LIST_ID} className="nav-sublist" hidden={!open && !expanded}>
        {children.map((child) => (
          <li key={child.href}>
            <Link
              href={child.href}
              aria-current={pathname === child.href ? "page" : undefined}
              onClick={() => {
                setOpen(false);
                onNavigate();
              }}
            >
              {child.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
