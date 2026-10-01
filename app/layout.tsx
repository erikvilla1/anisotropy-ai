import type { Metadata } from "next";
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/manrope";
import "./globals.css";
import "./expansion.css";
import "./research.css";
import { SiteHeader, SiteFooter } from "@/components/site-shell";

export const metadata: Metadata = {
  title: "Anisotropy AI — From material to understanding",
  description:
    "An engineering intelligence platform connecting composite coupon design, physical testing, and traceable analysis. Explore the first chapter.",
  icons: {
    icon: { url: "/assets/brand/anisotropy-mark.svg", type: "image/svg+xml" },
    apple: "/assets/brand/anisotropy-logo.png",
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
      </body>
    </html>
  );
}
