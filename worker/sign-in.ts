/** Our own sign-in (ADR-0058): an invited email gets a six-digit code by email, the code buys a signed session cookie, and every
 * request to the site and the API needs that cookie. The API learns who is asking from a short-lived token the Worker signs
 * (`X-Anisotropy-Identity`), which it checks with the same secret (api/src/anisotropy_api/access.py). Pure: no Cloudflare
 * imports, so `tests/worker-sign-in.test.ts` runs it in Node; worker/index.ts wires it to the runtime. */

export const SESSION_COOKIE = "__Host-anisotropy-session";
export const IDENTITY_HEADER = "X-Anisotropy-Identity";
export const SESSION_SECONDS = 7 * 24 * 3600;
export const IDENTITY_SECONDS = 120;
export const IDENTITY_AUDIENCE = "anisotropy-api";
export const IDENTITY_ISSUER = "anisotropy-sign-in";
export const CODE_SECONDS = 10 * 60;
export const CODE_ATTEMPTS = 5;
export const RESEND_SECONDS = 30;
export const SENDS_PER_HOUR = 5;

/** The Worker's settings for the sign-in: all four or none (ADR-0003). None keeps the Worker as it was, behind Cloudflare Access. */
export const SIGN_IN_VARIABLES = ["ANISOTROPY_SESSION_SECRET", "ANISOTROPY_INVITED", "RESEND_API_KEY", "ANISOTROPY_EMAIL_FROM"] as const;

export interface SignInConfig {
  secret: string;
  invited: Invited;
  resendKey: string;
  emailFrom: string;
}

export interface Invited {
  emails: ReadonlySet<string>;
  domains: ReadonlySet<string>;
}

const EMAIL = /^[^\s@<>()",;:]+@[a-z0-9-]+(\.[a-z0-9-]+)+$/;

export function normalizeEmail(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const email = raw.trim().toLowerCase();
  return email.length <= 254 && EMAIL.test(email) ? email : null;
}

/** The invite list as a variable: emails and `@domain` entries, separated by commas, spaces or new lines. */
export function parseInvited(text: string): Invited {
  const emails = new Set<string>();
  const domains = new Set<string>();
  for (const entry of text.split(/[\s,;]+/).map((part) => part.trim().toLowerCase()).filter(Boolean)) {
    if (entry.startsWith("@")) {
      if (!/^@[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(entry)) throw new Error(`ANISOTROPY_INVITED: ${entry} is not a domain`);
      domains.add(entry.slice(1));
    } else {
      const email = normalizeEmail(entry);
      if (email === null) throw new Error(`ANISOTROPY_INVITED: ${entry} is not an email address`);
      emails.add(email);
    }
  }
  if (emails.size === 0 && domains.size === 0) throw new Error("ANISOTROPY_INVITED lists nobody");
  return { emails, domains };
}

export function isInvited(email: string, invited: Invited): boolean {
  return invited.emails.has(email) || invited.domains.has(email.slice(email.lastIndexOf("@") + 1));
}

/** The settings from the Worker's environment; null when none is set, an error naming the gap when some are. */
export function signInConfig(env: object): SignInConfig | null {
  const values = Object.fromEntries(SIGN_IN_VARIABLES.map((name) => {
    const value: unknown = Reflect.get(env, name);
    return [name, typeof value === "string" && value.trim() !== "" ? value.trim() : null];
  })) as Record<(typeof SIGN_IN_VARIABLES)[number], string | null>;
  if (Object.values(values).every((value) => value === null)) return null;
  const missing = SIGN_IN_VARIABLES.filter((name) => values[name] === null);
  if (missing.length > 0) throw new Error(`${missing.join(", ")} not set: the sign-in needs all of ${SIGN_IN_VARIABLES.join(", ")}`);
  const secret = values.ANISOTROPY_SESSION_SECRET!;
  if (secret.length < 32) throw new Error("ANISOTROPY_SESSION_SECRET must be at least 32 characters (openssl rand -base64 48)");
  return { secret, invited: parseInvited(values.ANISOTROPY_INVITED!), resendKey: values.RESEND_API_KEY!, emailFrom: values.ANISOTROPY_EMAIL_FROM! };
}

// --- Signing ---------------------------------------------------------------------------------------------------------------

const encoder = new TextEncoder();

function base64url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64url(text: string): Uint8Array<ArrayBuffer> | null {
  if (!/^[A-Za-z0-9_-]*$/.test(text)) return null;
  const binary = atob(text.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (text.length % 4)) % 4));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

async function hmacKey(raw: Uint8Array): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", new Uint8Array(raw), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

/** One key per use, derived from the one secret: HMAC-SHA256(secret, label). The API derives the identity key the same way. */
export async function deriveKey(secret: string, purpose: "session" | "identity"): Promise<CryptoKey> {
  const root = await hmacKey(encoder.encode(secret));
  const derived = new Uint8Array(await crypto.subtle.sign("HMAC", root, encoder.encode(`anisotropy ${purpose} v1`)));
  return hmacKey(derived);
}

async function sign(key: CryptoKey, text: string): Promise<string> {
  return base64url(new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(text))));
}

/** The session cookie's value: `v1.<payload>.<signature>`, the payload naming the email and the expiry in seconds. */
export async function signSession(key: CryptoKey, email: string, now: number): Promise<string> {
  const payload = base64url(encoder.encode(JSON.stringify({ e: email, x: Math.floor(now / 1000) + SESSION_SECONDS })));
  return `v1.${payload}.${await sign(key, `v1.${payload}`)}`;
}

/** The email a session cookie vouches for, or null when it is missing, altered, malformed or expired. */
export async function readSession(key: CryptoKey, value: string | null, now: number): Promise<string | null> {
  if (!value) return null;
  const [version, payload, signature, ...rest] = value.split(".");
  if (version !== "v1" || !payload || !signature || rest.length > 0) return null;
  const signatureBytes = fromBase64url(signature);
  if (signatureBytes === null) return null;
  const valid = await crypto.subtle.verify("HMAC", key, signatureBytes, encoder.encode(`v1.${payload}`));
  if (!valid) return null;
  try {
    const bytes = fromBase64url(payload);
    const claims: unknown = bytes && JSON.parse(new TextDecoder().decode(bytes));
    if (typeof claims !== "object" || claims === null) return null;
    const { e, x } = claims as { e?: unknown; x?: unknown };
    if (typeof e !== "string" || typeof x !== "number" || x * 1000 <= now) return null;
    return normalizeEmail(e);
  } catch {
    return null;
  }
}

/** The token the API checks: a JWT (HS256) for the API's audience, two minutes long. */
export async function identityToken(key: CryptoKey, email: string, now: number): Promise<string> {
  const iat = Math.floor(now / 1000);
  const header = base64url(encoder.encode(JSON.stringify({ alg: "HS256", typ: "JWT" })));
  const claims = { aud: IDENTITY_AUDIENCE, email, exp: iat + IDENTITY_SECONDS, iat, iss: IDENTITY_ISSUER };
  const body = base64url(encoder.encode(JSON.stringify(claims)));
  return `${header}.${body}.${await sign(key, `${header}.${body}`)}`;
}

// --- Cookies and addresses -------------------------------------------------------------------------------------------------

export function readCookie(header: string | null, name: string): string | null {
  for (const part of (header ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index > 0 && part.slice(0, index).trim() === name) return part.slice(index + 1).trim();
  }
  return null;
}

export function sessionCookie(value: string): string {
  return `${SESSION_COOKIE}=${value}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Lax`;
}

export function clearedCookie(): string {
  return `${SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;
}

/** Where to go after signing in: a path on this site, never another site (`//evil.example`, `/\evil.example`). */
export function safeNext(raw: unknown): string {
  if (typeof raw !== "string" || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return "/";
  if (/[\u0000-\u001f]/.test(raw) || raw.startsWith("/sign-in") || raw.startsWith("/sign-out")) return "/";
  return raw;
}

// --- Codes -----------------------------------------------------------------------------------------------------------------

/** Where the codes live: a Durable Object's storage in the Worker, a Map in the tests. */
export interface CodeStore {
  get(key: string): Promise<CodeRecord | undefined>;
  put(key: string, value: CodeRecord): Promise<void>;
  delete(key: string): Promise<unknown>;
}

export interface CodeRecord {
  hash: string | null;
  expires: number;
  attempts: number;
  sent: number[];
}

export type Issued = { code: string } | { waitSeconds: number };

async function codeHash(email: string, code: string): Promise<string> {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(`${email}:${code}`)));
  return base64url(digest);
}

function randomCode(): string {
  const buffer = new Uint32Array(1);
  for (;;) {  // reject the top of the range so every code is equally likely
    crypto.getRandomValues(buffer);
    if (buffer[0] < 4_294_000_000) return String(buffer[0] % 1_000_000).padStart(6, "0");
  }
}

/** A new code for an email, replacing the last one; or how long to wait when codes were sent too recently or too often. */
export async function issueCode(store: CodeStore, email: string, now: number, makeCode: () => string = randomCode): Promise<Issued> {
  const record = await store.get(email);
  const sent = (record?.sent ?? []).filter((time) => now - time < 3600_000);
  const last = sent.at(-1);
  if (last !== undefined && now - last < RESEND_SECONDS * 1000) return { waitSeconds: Math.ceil((RESEND_SECONDS * 1000 - (now - last)) / 1000) };
  if (sent.length >= SENDS_PER_HOUR) return { waitSeconds: Math.ceil((sent[0] + 3600_000 - now) / 1000) };
  const code = makeCode();
  await store.put(email, { hash: await codeHash(email, code), expires: now + CODE_SECONDS * 1000, attempts: 0, sent: [...sent, now] });
  return { code };
}

/** Whether a typed code is the email's current one. A right code is used up; five wrong ones use the code up too. */
export async function checkCode(store: CodeStore, email: string, typed: unknown, now: number): Promise<boolean> {
  const record = await store.get(email);
  if (!record || record.hash === null || record.expires <= now) return false;
  const code = typeof typed === "string" ? typed.replace(/\s+/g, "") : "";
  const matches = /^\d{6}$/.test(code) && timingSafeEqual(await codeHash(email, code), record.hash);
  const attempts = record.attempts + 1;
  const spent = matches || attempts >= CODE_ATTEMPTS;
  await store.put(email, { ...record, hash: spent ? null : record.hash, attempts });
  return matches;
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let index = 0; index < a.length; index += 1) diff |= a.charCodeAt(index) ^ b.charCodeAt(index);
  return diff === 0;
}

// --- The email -------------------------------------------------------------------------------------------------------------

/** The request that sends a code through Resend's API (https://resend.com/docs/api-reference/emails/send-email). */
export function codeEmailRequest(config: SignInConfig, to: string, code: string): Request {
  const text = [
    `Your Anisotropy Studio sign-in code is ${code}.`,
    "",
    `It works once, for ${CODE_SECONDS / 60} minutes. If you did not try to sign in, ignore this email.`,
  ].join("\n");
  const html = `<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.6;color:#111">`
    + `<p>Your Anisotropy Studio sign-in code is</p>`
    + `<p style="font-size:28px;font-weight:600;letter-spacing:6px;margin:8px 0 16px">${code}</p>`
    + `<p style="color:#555">It works once, for ${CODE_SECONDS / 60} minutes. If you did not try to sign in, ignore this email.</p></div>`;
  return new Request("https://api.resend.com/emails", {
    method: "POST",
    headers: { authorization: `Bearer ${config.resendKey}`, "content-type": "application/json" },
    body: JSON.stringify({ from: config.emailFrom, to: [to], subject: `${code} is your Anisotropy sign-in code`, text, html }),
  });
}
