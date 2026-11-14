import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { findService, serviceHref, services, statusLabel } from "../lib/services";
import { SERVICES_PANEL_IN_HEADER, primaryNav, servicesNav, siteNav } from "../lib/site-nav";

// The site map of ADR-0058: five services, each with a page, and a header without Calculator or Studio.

test("the five services are unique, ordered as the audit lists them, and each has a page file", () => {
  const slugs = services.map((service) => service.slug);
  assert.deepEqual(slugs, [
    "computer-aided-design",
    "finite-element-modeling",
    "test-plans",
    "documentation",
    "manufacturing-plans",
  ]);
  assert.equal(new Set(slugs).size, slugs.length);
  for (const service of services) {
    assert.ok(existsSync(join(process.cwd(), "app", "services", service.slug, "page.tsx")), `${service.slug} has no page`);
    assert.equal(serviceHref(service), `/services/${service.slug}`);
    assert.ok(service.summary.length > 20, `${service.slug} summary`);
    assert.ok(statusLabel[service.status]);
    assert.match(service.access.href, /^\/(workspace(\/[a-z]+)?|contact)$/); // the workspace since ADR-0062
  }
  assert.equal(findService("finite-element-modeling")?.status, "built");
  assert.equal(findService("manufacturing-plans")?.status, "planned");
  assert.equal(findService("nowhere"), undefined);
});

test("the site's navigation is About, Industries, Resources, Services and Contact, with the services under Services", () => {
  assert.deepEqual(
    siteNav.map((item) => item.label),
    ["About", "Industries", "Resources", "Services", "Contact us"],
  );
  const labels = siteNav.flatMap((item) => [item.label, ...(item.children ?? []).map((child) => child.label)]);
  assert.ok(!labels.includes("Calculator"));
  assert.ok(!labels.includes("Studio"));
  assert.deepEqual(
    servicesNav.children?.map((child) => child.href),
    services.map(serviceHref),
  );
  for (const item of siteNav) assert.ok(existsSync(join(process.cwd(), "app", item.href.slice(1), "page.tsx")), `${item.href} has no page`);
});

test("the header shows the same items, Services as a plain link while its panel is hidden (ADR-0058 amendment 4)", () => {
  assert.deepEqual(primaryNav.map((item) => [item.label, item.href]), siteNav.map((item) => [item.label, item.href]));
  assert.equal(primaryNav.some((item) => item.children), SERVICES_PANEL_IN_HEADER);
});
