import { Fragment } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

type BandLink = { label: string; href: string };

/** The closing section of a page (ADR-0077): a band of the section kit (`app/sections.css`), light but for the home page's
 * (`dark`), with a monospace label, the
 * statement as a large heading in the left half, the page's one action from the halfway line (column 7, where the footer's
 * columns start), and an optional quiet row of links under a 1 px rule on the same columns. The home
 * page, the industries page and the services page use it, so they cannot drift. Its rules are `.closing-band` in
 * `app/globals.css`. Its links stay on the site, so their arrow points right; ↗ is kept for a link that opens a new tab. */
export function ClosingBand({ label, heading, action, links, dark }: {
  /** The small line above the statement. */
  label: string;
  /** The statement, one entry per line. */
  heading: readonly string[];
  /** The page's one action, the filled button. */
  action: BandLink;
  /** The row under the rule: its label and its links. */
  links?: { label: string; items: readonly BandLink[] };
  /** On dark grey with light words and a white button, in place of white with dark ones (the home page's, ADR-0077
   * amendment 54, which ended amendment 49's light grey; the rule is in app/home.css). The band is then one of the kit's
   * dark bands, so everything in it reads the dark values. */
  dark?: boolean;
}) {
  return (
    <section className={`band ${dark ? "is-dark" : "is-light"} closing-band${links ? " has-links" : ""}`}>
      <p className="band-label">{label}</p>
      <div className="band-grid closing-band-main">
        <h2 className="closing-band-statement">
          {heading.map((line, index) => (
            <Fragment key={line}>
              {index > 0 ? <br /> : null}
              {line}
            </Fragment>
          ))}
        </h2>
        <Link className="button primary closing-band-action" href={action.href}>
          {action.label} <ArrowRight size={18} aria-hidden="true" />
        </Link>
      </div>
      {links ? (
        <div className="band-grid closing-band-links">
          <span>{links.label}</span>
          <div>
            {links.items.map((item) => (
              <Link href={item.href} key={item.href}>
                {item.label}
                {/* A no-break space inside a no-wrap span: the arrow stays with the last word when the link wraps. */}
                <span>
                  {"\u00a0"}
                  <ArrowRight size={16} aria-hidden="true" />
                </span>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
