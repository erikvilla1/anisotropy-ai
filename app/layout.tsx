import type { Metadata } from "next";
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/manrope";
import "katex/dist/katex.min.css";
import "./globals.css";
import "./expansion.css";
import "./research.css";
import "./provenance.css";
import "./sections.css";
import "./brand.css";
import { SiteHeader, SiteFooter } from "@/components/site-shell";
import { PageTransition } from "@/components/page-transition";

export const metadata: Metadata = {
  title: "Anisotropy — Composites. Calculated.",
  description:
    "An engineering intelligence platform connecting composite coupon design, physical testing, and traceable analysis. Explore the first chapter.",
  icons: {
    icon: { url: "/assets/brand/anisotropy-icon.svg", type: "image/svg+xml" },
    apple: "/assets/brand/anisotropy-touch-icon.png",
  },
};
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
