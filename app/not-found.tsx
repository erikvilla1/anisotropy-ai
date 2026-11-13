import type { Metadata } from "next";
import Link from "next/link";
import "./inner-pages.css";

// The 404 page's own title, after the site's template; Next adds noindex to it by itself.
export const metadata: Metadata = {
  title: "Page not found",
  description: "The address may be mistyped, or the page has moved.",
};

/** Any address the site does not have (the hosted Worker serves this page with status 404): the site's own header, opening and
 * footer on the page ground, with the way home and to the workspace. */
export default function NotFound() {
  return (
    <main id="main" className="kit-page not-found-page">
      <section className="page-opening">
        <p className="page-opening-label">404</p>
        <h1 className="page-opening-title">Page not found</h1>
        <div className="page-opening-grid">
          <div className="page-opening-copy">
            <p>The address may be mistyped, or the page has moved.</p>
            <div className="not-found-links">
              <Link className="button primary" href="/">
                Home
              </Link>
              <Link className="kit-link" href="/workspace">
                Workspace
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
