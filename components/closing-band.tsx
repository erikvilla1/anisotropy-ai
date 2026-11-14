import { Fragment } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

type BandLink = { label: string; href: string };

/** The closing section of a page (ADR-0077): a light band of the section kit (`app/sections.css`) with a monospace label, the
 * statement as a large heading in the left half, the page's one action from the halfway line (column 7, where the header's
 * links and the footer's columns start), and an optional quiet row of links under a 1 px rule on the same columns. The home
 * page and the industries page both use it, so the two cannot drift. Its rules are `.closing-band` in `app/globals.css`. */
export function ClosingBand({ label, heading, action, links, grey }: {
  /** The small line above the statement. */
  label: string;
  /** The statement, one entry per line. */
  heading: readonly string[];
  /** The page's one action, the filled button. */
  action: BandLink;
  /** The row under the rule: its label and its links. */
  links?: { label: string; items: readonly BandLink[] };
  /** On light grey in place of white (the home page's, ADR-0077 amendment 49; the rule is in app/home.css). */
  grey?: boolean;
}) {
  return (
    <section className={`band is-light closing-band${links ? " has-links" : ""}${grey ? " is-grey" : ""}`}>
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
          {action.label} <ArrowUpRight size={18} />
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
                  <ArrowUpRight size={16} />
                </span>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
