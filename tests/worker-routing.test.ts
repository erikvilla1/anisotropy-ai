// The Worker's pure decisions (ADR-0056): which paths are the API's and what the container gets as its environment.
import assert from "node:assert/strict";
import { test } from "node:test";

import { CONTAINER_VARIABLES, apiPath, containerEnvironment } from "../worker/routing";

test("the API's paths lose their /api prefix and everything else is the site's", () => {
  assert.equal(apiPath("/api/v1/coupon-jobs"), "/v1/coupon-jobs");
  assert.equal(apiPath("/api/v1/coupon-jobs/abc/files/fields"), "/v1/coupon-jobs/abc/files/fields");
  assert.equal(apiPath("/api/healthz"), "/healthz");
  assert.equal(apiPath("/api/docs"), "/docs");
  assert.equal(apiPath("/api"), "/");
  assert.equal(apiPath("/api/"), "/");
  for (const site of ["/", "/studio", "/studio/", "/chat", "/calculator", "/apix", "/apix/v1", "/v1/runs", "/_next/static/x.js"]) {
    assert.equal(apiPath(site), null, site);
  }
});

test("the container receives the set, non-blank variables the API reads, and nothing else", () => {
  const env = {
    DATABASE_URL: "postgresql://u:p@h/db?sslmode=require", ANISOTROPY_R2_BUCKET: " ", ANISOTROPY_ACCESS_AUD: "",
    ANISOTROPY_ACCESS_TEAM_DOMAIN: "team.cloudflareaccess.com", API: { kind: "a binding" }, ASSETS: { kind: "a binding" },
    SOMETHING_ELSE: "not for the container", ANISOTROPY_GIT_COMMIT: "0123456789abcdef0123456789abcdef01234567",
  };
  assert.deepEqual(containerEnvironment(env), {
    DATABASE_URL: "postgresql://u:p@h/db?sslmode=require",
    ANISOTROPY_ACCESS_TEAM_DOMAIN: "team.cloudflareaccess.com",
    ANISOTROPY_GIT_COMMIT: "0123456789abcdef0123456789abcdef01234567",
  });
  assert.deepEqual(containerEnvironment({}), {});
  for (const name of ["DATABASE_URL", "ANISOTROPY_ACCESS_TEAM_DOMAIN", "ANISOTROPY_ACCESS_AUD", "ANISOTROPY_R2_BUCKET", "ANISOTROPY_R2_ENDPOINT",
                      "ANISOTROPY_R2_ACCESS_KEY_ID", "ANISOTROPY_R2_SECRET_ACCESS_KEY", "ANTHROPIC_API_KEY", "ANISOTROPY_GIT_COMMIT"]) {
    assert.ok((CONTAINER_VARIABLES as readonly string[]).includes(name), `${name} is one the API reads`);
  }
});
