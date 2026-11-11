"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import type { NavItem } from "@/lib/site-nav";
import { serviceHref, services, statusLabel } from "@/lib/services";
import "./services-menu.css";

const LIST_ID = "services-menu";
/** Anduril's menu starts to open about 100 to 150 ms after the pointer arrives and starts to close about 150 to 200 ms
 * after it leaves (measured 2026-11-10), so a pointer that only crosses the item opens nothing. */
const OPEN_DELAY_MS = 120;
const CLOSE_DELAY_MS = 150;

/** The Services item of the header: a link to the landing page plus a disclosure that opens a full-width panel under the
 * header, after Anduril's menu: a label and one paragraph on the left, the five service pages as large links from the
 * halfway line, each with how much of it exists. Disclosure pattern (a button with aria-expanded and a plain list), not a
 * menu role, so every entry stays an ordinary link. The stylesheet draws the panel, the header's ground and the blurred
 * layer over the page; on narrow screens it shows the list inside the open mobile navigation and hides the button. */
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
  const panel = useRef<HTMLDivElement>(null);
  const focusIndex = useRef<number | null>(null);
  const openTimer = useRef<number | null>(null);
  const closeTimer = useRef<number | null>(null);
  /** True while the panel is open only because the pointer is over it: a click on the button then keeps it open. */
  const openedByHover = useRef(false);
  const children = item.children ?? [];
  const statusOf = new Map(services.map((service) => [serviceHref(service), statusLabel[service.status]]));

  function clearTimers() {
    if (openTimer.current) window.clearTimeout(openTimer.current);
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    openTimer.current = closeTimer.current = null;
  }
  function close() {
    clearTimers();
    openedByHover.current = false;
    setOpen(false);
  }

  useEffect(() => {
    close();
  }, [pathname]);
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) close();
    }
    // Escape closes the panel wherever the focus is; it goes back to the button only if it was inside the menu.
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      if (root.current?.contains(document.activeElement)) button.current?.focus();
      close();
    }
    // The header scrolls away with the page; once the panel has left the screen the layer over the page goes too.
    function onScroll() {
      if ((panel.current?.getBoundingClientRect().bottom ?? 1) <= 0) close();
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", onScroll);
    };
  }, [open]);
  useEffect(() => {
    if (!open || focusIndex.current === null) return;
    links()[focusIndex.current]?.focus();
    focusIndex.current = null;
  }, [open]);
  useEffect(() => clearTimers, []);

  function links(): HTMLAnchorElement[] {
    return Array.from(root.current?.querySelectorAll<HTMLAnchorElement>(`#${LIST_ID} a`) ?? []);
  }
  function openAndFocus(index: number) {
    clearTimers();
    openedByHover.current = false;
    if (open || expanded) links()[index]?.focus();
    else {
      focusIndex.current = index;
      setOpen(true);
    }
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const all = links();
    const current = all.indexOf(document.activeElement as HTMLAnchorElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      openAndFocus(current < 0 ? 0 : Math.min(current + 1, all.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (current > 0) all[current - 1]?.focus();
      else if (!expanded) {
        close();
        button.current?.focus();
      }
    }
  }
  function onBlur(event: FocusEvent<HTMLDivElement>) {
    // The focus moved to another element of the page. A click on the panel's empty ground moves it nowhere and closes nothing.
    if (event.relatedTarget && !root.current?.contains(event.relatedTarget as Node)) close();
  }
  function hoverOpen(event: ReactPointerEvent<HTMLDivElement>) {
    // A finger has no hover, and in the open mobile navigation the list is already there.
    if (event.pointerType === "touch" || expanded) return;
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = null;
    if (open || openTimer.current) return;
    openTimer.current = window.setTimeout(() => {
      openTimer.current = null;
      openedByHover.current = true;
      setOpen(true);
    }, OPEN_DELAY_MS);
  }
  function hoverClose(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.pointerType === "touch") return;
    if (openTimer.current) window.clearTimeout(openTimer.current);
    openTimer.current = null;
    closeTimer.current = window.setTimeout(close, CLOSE_DELAY_MS);
  }
  function onButtonClick() {
    clearTimers();
    // The pointer had already opened the panel on its way to the button: the click confirms it instead of closing it.
    if (open && openedByHover.current) openedByHover.current = false;
    else if (open) close();
    else setOpen(true);
  }
  const current = pathname === item.href || pathname.startsWith(`${item.href}/`);
  return (
    <>
      <div
        className={open ? "services-menu is-open" : "services-menu"}
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
          className="services-menu-button"
          ref={button}
          aria-expanded={open}
          aria-controls={LIST_ID}
          aria-label="Show services"
          onClick={onButtonClick}
        >
          <span className="services-menu-plus" aria-hidden="true" />
        </button>
        <div className="services-panel" ref={panel}>
          <div className="services-panel-intro">
            <p className="services-panel-label">{item.label}</p>
            {/* The home page's introduction to its Platform section (app/page.tsx), word for word: it counts the statuses
                in lib/services.ts, so it changes when they do. */}
            <p>
              The same coupon record feeds every service. Two are built, two exist in part, one is stated as planned; each
              page says which.
            </p>
          </div>
          <ul id={LIST_ID} className="services-panel-list">
            {children.map((child, index) => {
              const status = statusOf.get(child.href);
              return (
                <li key={child.href}>
                  <Link
                    href={child.href}
                    aria-current={pathname === child.href ? "page" : undefined}
                    aria-describedby={status ? `${LIST_ID}-status-${index}` : undefined}
                    onClick={() => {
                      close();
                      onNavigate();
                    }}
                  >
                    {child.label}
                  </Link>
                  {status ? (
                    <span className="services-panel-status" id={`${LIST_ID}-status-${index}`}>
                      {status}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
      <div className="services-backdrop" aria-hidden="true" />
    </>
  );
}
