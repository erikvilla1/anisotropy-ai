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
 * kinds is a coupon. */
export type FeaAnalysis = "none" | "coupon";

/** The wing's page (ADR-0118), a page of the FEA section since the wing joined it (ADR-0118 amendment 1). */
export const WING_HREF = `${WORKSPACE_ROOT}/wing`;

/** The repair's page (ADR-0135), a page of the FEA section like the wing's. */
export const REPAIR_HREF = `${WORKSPACE_ROOT}/repair`;

/** A kind of FEA work. A coupon is set up in the FEA project itself; a wing is a project of its own kind (ADR-0122) worked on its own
 * page, `href`, under FEA (ADR-0118 amendment 1); a stepped patch repair is worked on its own page too, kept in the browser as its
 * repair file (ADR-0135). */
export type FeaKindId = Exclude<FeaAnalysis, "none"> | "wing" | "repair";
export type FeaKind = { id: FeaKindId; title: string; detail: string; href?: string };
export const FEA_KINDS: readonly FeaKind[] = [
  { id: "coupon", title: "Coupon test", detail: "A test coupon in tension, compression, shear or bending, set up from its material and layup." },
  { id: "wing", title: "Wing analysis", detail: "A composite wing over its flight envelope: every case's margins, stiffness and mass as you change it.", href: WING_HREF },
  { id: "repair", title: "Patch repair", detail: "A stepped patch bonded to a laminate: the bondline's stresses by hand as you change it, and its slice solved on request.", href: REPAIR_HREF },
];

/** The kinds a model reading a question may offer to set up (`/v1/workspace/questions`): those whose page it has been taught. A patch
 * repair is reached by its own fixed words until its chat is built (ADR-0135). */
export const ASKED_KINDS: readonly FeaKindId[] = FEA_KINDS.map((k) => k.id).filter((id) => id !== "repair");

export function feaKind(id: FeaKindId): FeaKind {
  const found = FEA_KINDS.find((k) => k.id === id);
  if (!found) throw new Error(`no kind of FEA work ${id}`);
  return found;
}

/** The FEA page set up for a coupon: the address of every link that promises one (ADR-0124). */
export const COUPON_HREF = `${WORKSPACE_ROOT}/fea?for=coupon`;
