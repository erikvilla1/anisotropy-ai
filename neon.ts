// The Neon project's settings for the hosted run records, read by the Neon CLI; a new branch expires after 7 days (ADR-0025 amendment 1).
import { defineConfig } from "@neon/config/v1";

export default defineConfig({
  auth: false,
  branch: (branch) => {
    if (branch.isDefault) {
      return {};
    }
    if (!branch.exists) {
      return { ttl: "7d" };
    }
    return {};
  },
});
