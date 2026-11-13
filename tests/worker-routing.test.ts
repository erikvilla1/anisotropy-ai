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

test("the API's container is told to queue jobs only when the Worker has the queue", async () => {
  const { apiEnvironment, isSolverPath, solverEnvironment } = await import("../worker/routing");
  const env = { DATABASE_URL: "postgresql://u:p@h/db", ANISOTROPY_ACCESS_AUD: "aud", ANISOTROPY_JOBS_PER_USER_PER_DAY: "20" };
  assert.deepEqual(apiEnvironment(env), { DATABASE_URL: "postgresql://u:p@h/db", ANISOTROPY_ACCESS_AUD: "aud", ANISOTROPY_JOBS_PER_USER_PER_DAY: "20" });
  assert.equal(apiEnvironment({ ...env, JOB_QUEUE: { kind: "a binding" } }).ANISOTROPY_JOB_ROLE, "queue");
  // a solver gets the database, the store and the role; no sign-in, origins, assistant or per-user cap
  assert.deepEqual(solverEnvironment({ ...env, ANISOTROPY_R2_BUCKET: "b", ANTHROPIC_API_KEY: "k", ANISOTROPY_ALLOWED_ORIGINS: "https://anisotropy.dev" }),
                   { DATABASE_URL: "postgresql://u:p@h/db", ANISOTROPY_R2_BUCKET: "b", ANISOTROPY_JOB_ROLE: "solver" });
  // who sees an upload and the connector's route (ADR-0094 step 5) reach the API's container and never a solver, which has no sign-in
  const uploads = { ANISOTROPY_FOUNDER_EMAILS: "founder@example.com", ANISOTROPY_CONNECTOR_UPLOADS: "on" };
  assert.deepEqual(apiEnvironment({ ...env, ...uploads }), { ...env, ...uploads });
  assert.deepEqual(solverEnvironment({ ...env, ...uploads }), { DATABASE_URL: "postgresql://u:p@h/db", ANISOTROPY_JOB_ROLE: "solver" });
  for (const path of ["/v1/solver", "/v1/solver/jobs/x", "/v1/solver/jobs/x/stop"]) assert.ok(isSolverPath(path), path);
  for (const path of ["/v1/coupon-jobs", "/v1/solvers", "/v1/coupon-jobs/v1/solver/"]) assert.ok(!isSolverPath(path), path);
});

test("the hosted container never gets the switch that shows every coupon test (ADR-0089): the hosted tier offers tension only", () => {
  assert.ok(!(CONTAINER_VARIABLES as readonly string[]).includes("ANISOTROPY_ALL_TESTS"));
  assert.deepEqual(containerEnvironment({ ANISOTROPY_ALL_TESTS: "on", ANISOTROPY_RUN_RECORDS: "off" }), { ANISOTROPY_RUN_RECORDS: "off" });
});
