import type { Metadata } from "next";
import { DataView } from "./data-view";

// Test-data checking has no submission yet, so this page stays out of search results and out of the site navigation.
export const metadata: Metadata = {
  title: "Test data",
  description: "Check a CSV of coupon results in your browser, or try the example. Nothing is uploaded.",
  robots: { index: false, follow: false },
};

export default function DataPage() {
  return <DataView />;
}
