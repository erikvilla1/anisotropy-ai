"use client";

import { useRouter } from "next/navigation";
import { LaminateChat } from "@/components/studio/laminate-chat";

/** The laminate response workspace (ADR-0062, part 2): the laminate assistant of ADR-0060 as it is, full width; its own panels, viewer and
 * assistant column come with part 5. "Back to the coupon tests" opens the coupon FEA workspace. */
export function LaminateWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  return <LaminateChat apiBaseUrl={apiBaseUrl} onBack={() => router.push("/workspace/fea")} />;
}
