/** The sign-in page (ADR-0058), in the studio's look: its colours and type (app/globals.css), the mark and the word Anisotropy.
 * Two steps on one page: the email, then the six-digit code. Plain HTML forms, no script, so it works before anything else on the
 * site has loaded. Everything the page shows from a request is escaped. */

import { MARK_DATA_URL } from "./brand-mark";
import { CODE_SECONDS } from "./sign-in";

export interface SignInView {
  step: "email" | "code";
  next: string;
  email?: string;
  notice?: string;
  error?: string;
}

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!);
}

const STYLE = `
:root{--bg:#0c0e0d;--panel:#121513;--raised:#181c19;--line:#2a2e2b;--text:#eef0e9;--muted:#9ba29b;--accent:#c1deb5;--ink:#17220f;
--font:"DM Sans",system-ui,-apple-system,"Segoe UI",Arial,sans-serif;--heading:"Manrope",system-ui,-apple-system,"Segoe UI",Arial,sans-serif;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0}
body{min-height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--text);font-family:var(--font);font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}
h1,p{margin:0}a{color:var(--accent)}
.bar{height:72px;padding:0 48px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}
.wordmark{display:flex;align-items:center;gap:10px;font-family:var(--heading);font-size:22px;font-weight:600;letter-spacing:-1px}
.wordmark img{width:40px;height:auto}
.tag{font-size:9px;letter-spacing:1.4px;color:#838b83;text-transform:uppercase}
main{flex:1;width:100%;max-width:1180px;margin:0 auto;padding:88px 48px 64px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,440px);gap:72px;align-items:start}
.eyebrow{font-size:10px;font-weight:500;letter-spacing:1.8px;text-transform:uppercase;color:var(--accent)}
h1{margin-top:14px;font-family:var(--heading);font-size:clamp(32px,4.4vw,48px);font-weight:500;line-height:1.08;letter-spacing:-1.6px}
.lede{margin-top:16px;max-width:520px;font-size:15px;color:var(--muted)}
.strip{margin-top:40px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);border-radius:8px;background:var(--panel);overflow:hidden}
.strip div{padding:12px 14px 14px;border-left:1px solid var(--line)}.strip div:first-child{border-left:0}
.strip span{display:block;font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted)}
.strip b{display:block;margin-top:4px;font-weight:400;font-size:13px}
.card{border:1px solid var(--line);border-radius:10px;background:var(--panel);overflow:hidden}
.card-head{display:flex;align-items:center;gap:9px;padding:14px 18px;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted)}
.dot{width:6px;height:6px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px #c1deb522}
.card-body{padding:22px 18px 20px}
.card-title{font-family:var(--heading);font-size:18px;font-weight:500}
.card-note{margin-top:4px;font-size:13px;color:var(--muted)}.card-note b{color:var(--text);font-weight:500}
.notice,.error{margin-top:16px;padding:10px 12px;border-radius:6px;font-size:13px}
.notice{border:1px solid #33452d;background:#141c12;color:var(--accent)}
.error{border:1px solid #5c4a2a;background:#1d1912;color:#f0d9a8}
form{margin:0}label{display:block;margin:18px 0 6px;font-size:12px;color:var(--muted)}
input{width:100%;height:44px;padding:0 12px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--text);font:inherit;font-size:14px}
input::placeholder{color:#6f766f}input:focus{outline:2px solid var(--accent);outline-offset:2px;border-color:var(--accent)}
input.code{font-size:22px;letter-spacing:8px;text-align:center}
button{width:100%;height:44px;margin-top:12px;border:1px solid var(--accent);border-radius:6px;background:var(--accent);color:var(--ink);font:inherit;font-size:14px;font-weight:600;cursor:pointer}
button:hover{filter:brightness(1.06)}button:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.links{margin-top:14px;display:flex;justify-content:space-between;gap:12px;font-size:12px}
.links button{width:auto;height:auto;margin:0;padding:0;border:0;background:none;color:var(--accent);font-size:12px;font-weight:400;text-decoration:underline}
.card-foot{padding:12px 18px;border-top:1px solid var(--line);background:var(--raised);font-size:12px;color:var(--muted)}
footer{padding:22px 48px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
@media (max-width:860px){.bar{height:64px;padding:0 16px}.wordmark{font-size:20px}.wordmark img{width:34px}
main{grid-template-columns:minmax(0,1fr);gap:32px;padding:40px 16px}.strip{grid-template-columns:repeat(2,minmax(0,1fr))}
.strip div:nth-child(3){border-left:0}.strip div:nth-child(n+3){border-top:1px solid var(--line)}footer{padding:18px 16px}}
@media (max-width:420px){.tag{display:none}}`;

function emailStep(view: SignInView): string {
  const next = escapeHtml(view.next);
  return `
<p class="card-title" id="card-title">Sign in to Anisotropy Studio</p>
<p class="card-note">Enter the email you were invited with and we'll send you a sign-in code.</p>
${messages(view)}
<form method="post" action="/sign-in/code">
  <input type="hidden" name="next" value="${next}" />
  <label for="email">Email</label>
  <input id="email" name="email" type="email" autocomplete="email" required autofocus placeholder="you@company.com" value="${escapeHtml(view.email ?? "")}" />
  <button type="submit">Send sign-in code</button>
</form>`;
}

function codeStep(view: SignInView): string {
  const next = escapeHtml(view.next);
  const email = escapeHtml(view.email ?? "");
  return `
<p class="card-title" id="card-title">Check your email</p>
<p class="card-note">If <b>${email}</b> is invited, a six-digit code is on its way. It works for ${CODE_SECONDS / 60} minutes.</p>
${messages(view)}
<form method="post" action="/sign-in/verify">
  <input type="hidden" name="next" value="${next}" />
  <input type="hidden" name="email" value="${email}" />
  <label for="code">Sign-in code</label>
  <input id="code" class="code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9 ]{6,7}" maxlength="7" required autofocus placeholder="000000" />
  <button type="submit">Sign in</button>
</form>
<div class="links">
  <a href="/sign-in?next=${encodeURIComponent(view.next)}">Use a different email</a>
  <form method="post" action="/sign-in/code">
    <input type="hidden" name="next" value="${next}" />
    <input type="hidden" name="email" value="${email}" />
    <button type="submit">Send a new code</button>
  </form>
</div>`;
}

function messages(view: SignInView): string {
  return (view.notice ? `<p class="notice" role="status">${escapeHtml(view.notice)}</p>` : "")
    + (view.error ? `<p class="error" role="alert">${escapeHtml(view.error)}</p>` : "");
}

export function signInPage(view: SignInView): string {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="color-scheme" content="dark" />
<meta name="robots" content="noindex" />
<title>Sign in · Anisotropy Studio</title>
<link rel="icon" href="${MARK_DATA_URL}" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=Manrope:wght@500;600&display=swap" />
<style>${STYLE}</style>
</head>
<body>
<header class="bar">
  <span class="wordmark"><img alt="" width="40" height="36" src="${MARK_DATA_URL}" /><span>Anisotropy</span></span>
  <span class="tag">Research preview / v.01</span>
</header>
<main>
  <section>
    <p class="eyebrow">Studio / Sign in</p>
    <h1>From the coupon to its stresses.</h1>
    <p class="lede">Anisotropy Studio is invite-only. Sign in with the email you were invited with and we send you a one-time code; no password to remember.</p>
    <div class="strip" aria-hidden="true">
      <div><span>Test</span><b>open-hole tension</b></div>
      <div><span>Material</span><b>IM7 / 8552</b></div>
      <div><span>Layup</span><b>[45/0/-45/90]s</b></div>
      <div><span>Solver</span><b>engine + CalculiX</b></div>
    </div>
  </section>
  <section class="card" aria-labelledby="card-title">
    <div class="card-head"><span class="dot"></span>Secure sign-in</div>
    <div class="card-body">${view.step === "email" ? emailStep(view) : codeStep(view)}</div>
    <div class="card-foot">No invite yet? Ask the Anisotropy team for access.</div>
  </section>
</main>
<footer>Anisotropy · anisotropy.dev</footer>
</body>
</html>`;
}
