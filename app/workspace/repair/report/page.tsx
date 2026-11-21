import type { Metadata } from "next";
import { RepairReport } from "@/components/workspace/repair-report";
import "../../../studio/studio.css";
import "../../workspace.css";
import "../../repair.css";

export const metadata: Metadata = {
  title: "Patch repair report",
  description: "The report of a stepped patch repair, laid out for paper: what it is, its slice, the bondline by hand and as a solved slice, and what the analysis is not.",
};

/** The repair's report (ADR-0135): the repair this browser holds, laid out for paper and saved as a PDF by the browser's print. */
export default function RepairReportPage() {
  return (
    <main id="main" className="studio-page repair-report-main">
      <RepairReport apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
