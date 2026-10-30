// The site as the hosted tier serves it (ADR-0056): the API at /api on the same origin, which the Worker forwards to the solver
// container. One script instead of `NEXT_PUBLIC_ANISOTROPY_API_URL=/api npm run build`, because that shell syntax differs
// between PowerShell and Git Bash, and Git Bash on Windows rewrites a value that starts with a slash into a C:\ path.
import { spawnSync } from "node:child_process";

const env = { ...process.env, NEXT_PUBLIC_ANISOTROPY_API_URL: "/api" };
const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const result = spawnSync(npx, ["next", "build"], { stdio: "inherit", env, shell: process.platform === "win32" });
process.exit(result.status ?? 1);
