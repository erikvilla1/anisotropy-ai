import type { Metadata, Viewport } from "next";
import "@fontsource-variable/inter/opsz.css";
import "./globals.css";
import "./expansion.css";
import "./research.css";
import "./provenance.css";
import "./sections.css";
import "./brand.css";
import { SiteHeader, SiteFooter } from "@/components/site-shell";
import { PageTransition } from "@/components/page-transition";

/* Every page's title is its bare name, which the template follows with the site's (ADR-0058 amendment 2); a page without one
 * takes the default. The shared image is app/opengraph-image.jpg, the approved logo on black cut to 1200 x 630, and
 * app/favicon.ico is the tab icon below at 16, 32 and 48 px, for the clients that ask for /favicon.ico. */
export const metadata: Metadata = {
  metadataBase: new URL("https://anisotropy.dev"),
  title: { default: "Anisotropy | Composites. Calculated.", template: "%s | Anisotropy" },
  description:
    "Composite laminates and coupons, calculated: a cited materials library, a laminate calculator and coupon finite element analysis, with every number traced to its source.",
  openGraph: { type: "website", siteName: "Anisotropy" },
  twitter: { card: "summary_large_image" },
  icons: {
    icon: { url: "/assets/brand/anisotropy-icon.svg", type: "image/svg+xml" },
    apple: "/assets/brand/anisotropy-touch-icon.png",
  },
};
/** The browser's own bar on a phone takes the header's colour. */
export const viewport: Viewport = { themeColor: "#0d0d0d" };
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <SiteHeader />
        {children}
        <SiteFooter />
        <PageTransition />
      </body>
    </html>
  );
}
