# ADR-0058: Our own email-code sign-in in the Worker replaces Cloudflare Access in front of the hosted tier

- Status: Proposed
- Date: 2026-11-05
- Decided by: the founder (the goal) | Drafted by: Claude Code
- Related: ADR-0056 (and its amendment 3), ADR-0026 amendment 1, `worker/sign-in.ts`, `worker/gate.ts`, `api/src/anisotropy_api/access.py`, `tests/worker-sign-in.test.ts`, `api/tests/test_identity.py`

## Context

ADR-0056 put Cloudflare Access in front of `anisotropy.dev`: an email allow list, one-time PINs, and the `Cf-Access-Jwt-Assertion` token the API checks. Its sign-in page is Cloudflare's. The founder, 2026-11-05: "i don't want this to be cloudflare front end sign in token, i want it to have anisotropy type of style sign in page", and after the page was branded through Access's settings, "that was the plan to not have anything cloudflare related".

What Access offers was checked in the founder's account the same day (ADR-0056 amendment 3): only the older login page settings (name, logo, header, message, background colour), which keep Cloudflare's header, card and the `<team>.cloudflareaccess.com` address. Access custom pages, an HTML template for the login page, are not offered on the account. Even with them, the address bar would show the team domain.

## Options considered

1. Keep Access with its older branding. Rejected by the founder: the page still looks like Cloudflare's.
2. Ask Cloudflare to enable Access custom pages. Our design inside Access, but the visitor still passes through `<team>.cloudflareaccess.com`, and the feature's availability on the plan is unknown (no evidence yet).
3. A hosted identity service (Clerk, Auth0, Stytch). Their pages are branded by plan and live on their domains or need a custom domain set up; a new vendor holds the user list. Not taken.
4. Our own sign-in in the Worker that already serves the site: our page at `anisotropy.dev/sign-in`, a six-digit code by email, a signed session cookie, and a token the API checks. Taken. ADR-0056 had chosen "no login code of our own"; this reverses that part, because the founder's requirement cannot be met by Access.

## Decision

- **Who:** the invite list is the Worker secret `ANISOTROPY_INVITED`: emails and `@domain` entries. It is read on every request, so removing someone ends their session at once.
- **The code:** an invited email gets a six-digit code from `crypto.getRandomValues`, sent through Resend's API (`RESEND_API_KEY`, from `ANISOTROPY_EMAIL_FROM`). It works once, for ten minutes; five wrong guesses use it up; codes go out at most every 30 s and five times an hour per email. Codes are stored hashed in one Durable Object (`SignInCodes`), so attempts are counted in one place. An email that is not invited gets the same page and no email.
- **The session:** a cookie `__Host-anisotropy-session` (HttpOnly, Secure, SameSite=Lax, seven days) holding the email and expiry, signed with HMAC-SHA256 under a key derived from `ANISOTROPY_SESSION_SECRET`. Sign-in forms refuse another site's `Origin`. `/sign-out` clears it.
- **The gate:** the Worker runs first for every request (`run_worker_first: true`). Without a session, a page redirects to `/sign-in?next=…` (a path on this site only), and `/api/*` answers 401.
- **The API:** the Worker strips any `X-Anisotropy-Identity` header the browser sent and adds its own, an HS256 JWT (`aud` anisotropy-api, `iss` anisotropy-sign-in, two minutes) under a second key derived from the same secret. The container gets the secret and checks the token (`access.py`); its email goes on run records and jobs as before (ADR-0026 amendment 1). While both are set, the API accepts this token or Access's, so the switch has no gap.
- **Off by default:** without the four sign-in settings the Worker behaves as before, behind Access. A partial set answers 503 rather than opening the site.
- The page is the studio's look (`worker/sign-in-page.ts`), plain HTML forms with no script, under a strict Content-Security-Policy.

## Why (evidence)

- The founder's requirement, quoted above, and the account check in ADR-0056 amendment 3.
- Tests: `tests/worker-sign-in.test.ts` (settings, invite list, cookie signing and tampering, the identity token, code expiry, attempts and send limits, and the whole flow through the gate with stand-ins) and `api/tests/test_identity.py` (the API side, including the same token as a fixed vector so the two languages agree byte for byte). The Worker was also run under `wrangler dev` (no container): `/` redirected to the sign-in, `/api/v1/materials` answered 401, the Durable Object issued and checked codes and remembered the 30 s limit, and an unreachable email service gave the page's error instead of a crash.
- Not yet verified (UNVERIFIED): an email delivered through Resend from `anisotropy.dev`, and the whole flow on the deployed Worker with the container.

## Consequences

- We now own sign-in code. The rules above are the attack surface: code guessing (at most 25 guesses an hour per email against a million codes), session forgery (needs the secret), and email delivery.
- New dependency: Resend (or another sender behind the same request), with DNS records on `anisotropy.dev` for the sending domain. Its free tier is assumed to cover the beta (no evidence yet).
- Rotating `ANISOTROPY_SESSION_SECRET` signs everyone out; the container must get the new value too (it does, through the deploy).
- Cloudflare stays as the host (Workers, Containers, R2), invisible to visitors. Access can be removed once the sign-in works on the live site.

## How we will know it was wrong

- Codes do not arrive or land in spam for invited engineers in the beta.
- A security review finds a way past the gate, or the team needs single sign-on (Google Workspace, Microsoft) that a code by email cannot give: then an identity provider behind this same gate.
