/** What the site check may write out (ADR-0138). The repository is public, so the run's log, its summary and its files are public too:
 * every text the check writes passes through `scrub` first, and anything shaped like a secret, a person's address or a signed link is
 * replaced. The check sees the site through a service token, which carries no email, so none should be there; this is the second lock. */

const HIDDEN = "[hidden]";

/** An email address. */
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g;
/** A signed token such as Cloudflare Access's (three base64url parts, the first a JSON header). */
const JWT = /\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}/g;
/** A link's query, which can carry a signature (the bucket's signed links) or a session: the address is kept, the query is not. */
const QUERY = /(https?:\/\/[^\s?#"'<>]+)\?[^\s"'<>]*/g;
/** The file bucket's own address, which names the storage account: kept out of the public log whole. */
const BUCKET = /\b[a-z0-9-]+\.r2\.cloudflarestorage\.com\b/gi;
/** A header line naming a secret, as a log of a request would print it. */
const SECRET_HEADER = /\b(cf-access-client-secret|cf-access-client-id|cf-access-jwt-assertion|cf_authorization|authorization|cookie|x-api-key)\s*[:=]\s*\S+/gi;
/** A long run of letters and digits with no space, as a key or a token is. A commit's 40 hexadecimal digits are public and kept. */
const LONG_TOKEN = /\b[A-Za-z0-9_-]{40,}\b/g;
const COMMIT = /^[0-9a-f]{40}$/;

/** The text with every secret, address, signed link and long token replaced. `secrets` are the run's own values (the token's two
 * halves), replaced wherever they appear, whatever their shape. */
export function scrub(text: string, secrets: readonly string[] = []): string {
  let out = text;
  for (const secret of secrets) if (secret && secret.length >= 6) out = out.split(secret).join(HIDDEN);
  return out.replace(SECRET_HEADER, (_, name: string) => `${name}: ${HIDDEN}`).replace(JWT, HIDDEN).replace(QUERY, "$1").replace(BUCKET, "[storage]")
    .replace(EMAIL, HIDDEN).replace(LONG_TOKEN, (found) => COMMIT.test(found) ? found : HIDDEN);
}

/** Every string in a value scrubbed, keys and all, for a file the check writes. */
export function scrubbed<T>(value: T, secrets: readonly string[] = []): T {
  if (typeof value === "string") return scrub(value, secrets) as T;
  if (Array.isArray(value)) return value.map((item) => scrubbed(item, secrets)) as T;
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => [scrub(key, secrets), scrubbed(item, secrets)])) as T;
  }
  return value;
}

/** The secrets of this run, from its environment: never written, and replaced if they ever reach a text. */
export function runSecrets(env: NodeJS.ProcessEnv = process.env): string[] {
  return ["CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET", "ANTHROPIC_API_KEY", "GITHUB_TOKEN"].map((name) => env[name]?.trim() ?? "").filter(Boolean);
}
