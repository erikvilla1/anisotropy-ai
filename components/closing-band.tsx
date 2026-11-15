import { Fragment } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

type BandLink = { label: string; href: string };

/** The closing section of a page (ADR-0077 amendment 75): a band of the section kit (`app/sections.css`), light but for
 * the home page's (`dark`), set in the site's own way of ending a page. Everything stands in the middle: a small monospace
 * label, the statement, and under it the page's one action, alone (amendment 76); across the band's foot lie a few
 * hairlines, a laminate's plies seen from the edge. The home page, the industries page and the services page use it,
 * so they cannot drift. Its rules are `.closing-band` in `app/globals.css`. Its action stays on the site, so its arrow
 * points right; an arrow up and to the right is kept for a link that opens a new tab. */
export function ClosingBand({ label, heading, action, dark }: {
  /** The small line above the statement. */
  label: string;
  /** The statement, one entry per line. */
  heading: readonly string[];
  /** The page's one action, the filled button. */
  action: BandLink;
  /** On dark grey with light words and a white button, in place of white with dark ones (the home page's, ADR-0077
   * amendment 54; the rule is in app/home.css). The band is then one of the kit's dark bands, so everything in it reads
   * the dark values. */
  dark?: boolean;
}) {
  return (
    <section className={`band ${dark ? "is-dark" : "is-light"} closing-band`}>
      <p className="closing-band-label">{label}</p>
      <h2 className="closing-band-statement">
        {heading.map((line, index) => (
          <Fragment key={line}>
            {index > 0 ? <br /> : null}
            {line}
          </Fragment>
        ))}
      </h2>
      <div className="closing-band-actions">
        <Link className="button primary closing-band-action" href={action.href}>
          {action.label} <ArrowRight size={18} aria-hidden="true" />
        </Link>
      </div>
      <div className="closing-band-plies" aria-hidden="true" />
    </section>
  );
}
