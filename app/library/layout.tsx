import type { Metadata } from "next";

// The library page is a client component, so its title and description live here.
export const metadata: Metadata = {
  title: "Materials library",
  description: "Composite material properties in English and SI units, each value cited to its source page.",
};

export default function LibraryLayout({ children }: { children: React.ReactNode }) {
  return children;
}
