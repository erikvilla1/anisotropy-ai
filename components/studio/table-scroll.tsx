import type { ReactNode } from "react";

/** A wide table's box (style guide, Tables and numbers): it scrolls sideways inside its panel, and it is a named region the keyboard can
 * reach, so the columns past the panel's edge can be scrolled to with the arrow keys (WCAG 2.1.1, audit fea-run-9); the focus ring is
 * `.studio-table-scroll:focus-visible`. Every wide table of the coupon workspace and its results sits in one (the laminate workspace's
 * tables do not yet). */
export function TableScroll({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="studio-table-scroll" tabIndex={0} role="region" aria-label={label}>
      {children}
    </div>
  );
}
