/** The five services of the site map (ADR-0058): one page each under /services/<slug>.
 * Order follows the audit of 2026-10-31. `status` says how much of the service exists today,
 * so every page and card labels planned work as planned (docs/brain/voice.md). */
export type ServiceStatus = "built" | "partly" | "planned";
export type Service = {
  slug: string;
  title: string;
  /** The short uppercase name used in eyebrows. */
  eyebrow: string;
  /** One sentence for the landing card and the home page. */
  summary: string;
  status: ServiceStatus;
  /** The link under "Access" on the service's page; the FEM page's link text is asserted by tests/browser/studio.spec.ts. */
  access: { label: string; href: string };
};

export const statusLabel: Record<ServiceStatus, string> = {
  built: "AVAILABLE",
  partly: "IN PART",
  planned: "PLANNED",
};

export const services: readonly Service[] = [
  {
    slug: "computer-aided-design",
    title: "Computer-aided design",
    eyebrow: "CAD",
    summary: "Coupon geometry stated as a few dimensions and meshed from them. A CAD file to take elsewhere is planned.",
    status: "partly",
    access: { label: "Open the workspace", href: "/workspace/fea" },
  },
  {
    slug: "finite-element-modeling",
    title: "Finite element modeling",
    eyebrow: "FEM",
    summary: "The ASTM D3039 tension coupon set up in the browser, checked, solved and shown ply by ply. More tests follow.",
    status: "built",
    access: { label: "Open the workspace", href: "/workspace/fea" },
  },
  {
    slug: "test-plans",
    title: "Test plans",
    eyebrow: "TEST PLANS",
    summary: "Coupons sized to ASTM D3039, with a setup check against its clauses before anything runs.",
    status: "partly",
    access: { label: "Describe a coupon", href: "/workspace/fea" },
  },
  {
    slug: "documentation",
    title: "Documentation",
    eyebrow: "DOCUMENTATION",
    summary: "Every solved coupon leaves a report, its Abaqus input file (.inp) and the reference check.",
    status: "built",
    access: { label: "Open the workspace", href: "/workspace/fea" },
  },
  {
    slug: "manufacturing-plans",
    title: "Manufacturing plans",
    eyebrow: "MANUFACTURING",
    summary: "A ply book and a cure cycle from the same layup and material record.",
    status: "planned",
    access: { label: "Contact us", href: "/contact" },
  },
];

export function findService(slug: string): Service | undefined {
  return services.find((service) => service.slug === slug);
}

export function serviceHref(service: Service): string {
  return `/services/${service.slug}`;
}
