/** The workspace's sections (ADR-0124): FEA, CAD and Laminate, in that order, each a tile on `/workspace` and a page of its own on the
 * shared shell. FEA opens blank and the chat or a pick sets it up for one kind of work, a coupon test today (`FEA_KINDS`). Each title is
 * the section's one name, written the same on its tile, its header, its project rows and its assistant (audit fea-screens-10). CAD is
 * a section again on the founder's word (ADR-0124, reversing decision D5 of ADR-0091 amendment 2); it is being built. */

export type WorkspaceId = "fea" | "cad" | "laminate";

export type Workspace = {
  id: WorkspaceId;
  title: string;
  eyebrow: string;
  /** One line under the title: what goes in and what comes out. */
  detail: string;
  href: string;
  /** Being built: the tile says so, and the page opens with what is there. */
  planned?: boolean;
};

export const WORKSPACE_ROOT = "/workspace";

export const WORKSPACES: readonly Workspace[] = [
  { id: "fea", title: "FEA", eyebrow: "FINITE ELEMENTS", detail: "Set up, solve and read a model ply by ply. Starts blank: say what you want to analyse.",
    href: `${WORKSPACE_ROOT}/fea` },
  { id: "cad", title: "CAD", eyebrow: "GEOMETRY", detail: "Shapes and dimensions for a model. Being built.", href: `${WORKSPACE_ROOT}/cad`, planned: true },
  { id: "laminate", title: "Laminate", eyebrow: "LAMINATE", detail: "ABD matrices, strains, ply stresses and first-ply failure for a laminate under loads.",
    href: `${WORKSPACE_ROOT}/laminate` },
];

export function workspace(id: WorkspaceId): Workspace {
  const found = WORKSPACES.find((w) => w.id === id);
  if (!found) throw new Error(`no workspace ${id}`);
  return found;
}

/** The kinds of work an FEA project is set up for (ADR-0124). "none" is a project not set up yet; a project kept before there were
 * kinds is a coupon. The wing joins here when its branch merges. */
export type FeaAnalysis = "none" | "coupon";

export type FeaKind = { id: Exclude<FeaAnalysis, "none">; title: string; detail: string };
export const FEA_KINDS: readonly FeaKind[] = [
  { id: "coupon", title: "Coupon test", detail: "A test coupon in tension, compression, shear or bending, set up from its material and layup." },
];

export function feaKind(id: Exclude<FeaAnalysis, "none">): FeaKind {
  const found = FEA_KINDS.find((k) => k.id === id);
  if (!found) throw new Error(`no kind of FEA work ${id}`);
  return found;
}

/** The FEA page set up for a coupon: the address of every link that promises one (ADR-0124). */
export const COUPON_HREF = `${WORKSPACE_ROOT}/fea?for=coupon`;
