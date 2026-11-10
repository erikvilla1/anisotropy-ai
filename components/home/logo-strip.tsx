"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { Supporter } from "@/lib/supporters";

/** The marquee's speed in pixels a second, as PhysicsX's strip drifts (measured there on 2026-11-10). */
const DRIFT_SPEED = 40;

/** A row of supporters' logos, after PhysicsX's strip (ADR-0077 amendment 14). While the logos fit the row they stand still,
 * from the left. Once they are wider than the row, the set is repeated once, hidden from assistive technology, and the two
 * drift left as a marquee at a steady speed. The marquee stops under the pointer and while it holds the keyboard's focus;
 * for a visitor who asked for reduced motion the logos wrap onto more rows instead (app/home.css). `label` names the row.
 * The logos are small files and load with the page, so none drifts into view still empty. */
export function LogoStrip({ supporters, label }: { supporters: readonly Supporter[]; label: string }) {
  const row = useRef<HTMLDivElement>(null);
  const set = useRef<HTMLUListElement>(null);
  // The seconds one pass of the set takes, or null while the logos fit and nothing moves.
  const [pass, setPass] = useState<number | null>(null);

  useEffect(() => {
    const frame = row.current;
    const list = set.current;
    if (!frame || !list) return;
    // The logos' own widths and the gaps between them, which do not depend on whether the row is moving or wrapped.
    const measure = () => {
      const gap = parseFloat(getComputedStyle(list).columnGap) || 0;
      const widths = Array.from(list.children, (item) => item.getBoundingClientRect().width);
      const width = widths.reduce((sum, value) => sum + value, 0) + gap * Math.max(0, widths.length - 1);
      setPass(width > frame.clientWidth + 1 ? (width + gap) / DRIFT_SPEED : null);
    };
    // The observer reports once when it starts, so the first measure needs no call of its own.
    const observer = new ResizeObserver(measure);
    observer.observe(frame);
    observer.observe(list);
    return () => observer.disconnect();
  }, [supporters]);

  const moving = pass !== null;
  const logos = (copy: boolean) => (
    <ul className="logo-strip-set" ref={copy ? undefined : set} aria-hidden={copy || undefined}>
      {supporters.map((supporter) => (
        <li key={supporter.src}>
          <img
            src={supporter.src}
            alt={copy ? "" : supporter.name}
            width={supporter.width}
            height={supporter.height}
            decoding="async"
          />
        </li>
      ))}
    </ul>
  );
  return (
    <div
      className={moving ? "logo-strip is-moving" : "logo-strip"}
      ref={row}
      role="group"
      aria-label={label}
      tabIndex={moving ? 0 : undefined}
      style={moving ? ({ "--logo-strip-pass": `${pass}s` } as CSSProperties) : undefined}
    >
      <div className="logo-strip-track">
        {logos(false)}
        {moving ? logos(true) : null}
      </div>
    </div>
  );
}
