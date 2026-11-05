import { serviceHref, services } from "./services";

/** The header's items in the order of the audit of 2026-10-31 (ADR-0058). Calculator and Studio left the
 * header: the calculator lives on the home page and the studio is reached from the finite element page. */
export type NavItem = {
  label: string;
  href: string;
  children?: readonly { label: string; href: string }[];
};

export const primaryNav: readonly NavItem[] = [
  { label: "About", href: "/about" },
  { label: "Industries", href: "/industries" },
  { label: "Materials library", href: "/library" },
  {
    label: "Services",
    href: "/services",
    children: services.map((service) => ({ label: service.title, href: serviceHref(service) })),
  },
  { label: "Contact us", href: "/contact" },
];
