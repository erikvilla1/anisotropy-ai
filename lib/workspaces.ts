/** The workspaces (ADR-0062): one per kind of work, each a tile on `/workspace` and a page of its own with the panels and the API endpoint it
 * needs. The chat's tool list (`chat-tools.ts`) names the same two kinds; a new capability is one entry here. Each title is the workspace's
 * one name, written the same on its tile, its header, its project rows and the assistant (audit fea-screens-10). CAD is not a workspace
 * until geometry from a file exists (decision D5, ADR-0091 amendment 2). */
import { chatTool } from "./chat-tools";

export type WorkspaceId = "fea" | "laminate";

export type Workspace = {
  id: WorkspaceId;
  title: string;
  eyebrow: string;
  /** One line under the title: what goes in and what comes out. */
  detail: string;
  href: string;
};

export const WORKSPACE_ROOT = "/workspace";

export const WORKSPACES: readonly Workspace[] = [
  { id: "fea", title: chatTool("coupon").title, eyebrow: "FINITE ELEMENTS", detail: chatTool("coupon").detail, href: `${WORKSPACE_ROOT}/fea` },
  { id: "laminate", title: chatTool("laminate").title, eyebrow: "LAMINATE", detail: chatTool("laminate").detail, href: `${WORKSPACE_ROOT}/laminate` },
];

export function workspace(id: WorkspaceId): Workspace {
  const found = WORKSPACES.find((w) => w.id === id);
  if (!found) throw new Error(`no workspace ${id}`);
  return found;
}
