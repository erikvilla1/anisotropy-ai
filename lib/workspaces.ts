/** The workspaces (ADR-0062): one per kind of work, each a tile on `/workspace` and a page of its own with the panels and the API endpoint it
 * needs. The chat's tool list (`chat-tools.ts`) names the same two built kinds; a new capability is one entry here. Nothing on a tile claims
 * more than the repository backs (ADR-0058): CAD is a placeholder until geometry from a file exists. */
import { chatTool } from "./chat-tools";

export type WorkspaceId = "fea" | "laminate" | "cad";
export type WorkspaceStatus = "built" | "planned";

export type Workspace = {
  id: WorkspaceId;
  title: string;
  eyebrow: string;
  /** One line under the title: what goes in and what comes out. */
  detail: string;
  href: string;
  status: WorkspaceStatus;
};

export const WORKSPACE_ROOT = "/workspace";

export const WORKSPACES: readonly Workspace[] = [
  { id: "fea", title: "Coupon FEA", eyebrow: "FINITE ELEMENTS", detail: chatTool("coupon").detail, href: `${WORKSPACE_ROOT}/fea`, status: "built" },
  { id: "laminate", title: chatTool("laminate").title, eyebrow: "LAMINATE", detail: chatTool("laminate").detail, href: `${WORKSPACE_ROOT}/laminate`, status: "built" },
  {
    id: "cad", title: "CAD", eyebrow: "GEOMETRY", status: "planned", href: `${WORKSPACE_ROOT}/cad`,
    detail: "geometry from a CAD file (STEP, IGES or STL) viewed and meshed here; today a coupon's geometry is the few rows of the FEA workspace, and a CAD file to take elsewhere is planned",
  },
];

export function workspace(id: WorkspaceId): Workspace {
  const found = WORKSPACES.find((w) => w.id === id);
  if (!found) throw new Error(`no workspace ${id}`);
  return found;
}
