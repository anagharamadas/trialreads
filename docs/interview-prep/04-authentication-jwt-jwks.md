# 04 — Authentication (JWT / JWKS)

## 1. The concept

Authentication answers "who is making this request?" The dominant pattern for APIs is
the **JSON Web Token (JWT)**: a signed, self-contained token the client sends on every
request (`Authorization: Bearer <jwt>`). A JWT has three base64url parts — **header**
(algorithm + key id), **payload** (claims: `sub` = user id, `exp` = expiry, `aud` =
audience, `iss` = issuer), and **signature**.

The core ideas:

- **Stateless auth.** The server *verifies the signature* instead of looking the token
  up in a session store — so any instance can authenticate any request with no shared
  state. That's what makes JWTs pair naturally with horizontal scaling.
- **Symmetric (HS256) vs. asymmetric (ES256/RS256) signing.** HS256 uses one shared
  secret to sign *and* verify — anyone who can verify can also forge. Asymmetric signing
  uses a **private key to sign** (only the auth server has it) and a **public key to
  verify** (safe to distribute) — so a resource server can verify without being able to
  mint tokens.
- **JWKS** (JSON Web Key Set) — the auth server publishes its public keys at a
  well-known URL; the `kid` in the token header selects which key verified it. This
  enables **key rotation** without redeploying verifiers.
- **What you must verify:** signature, `exp` (not expired), `aud`/`iss` (intended for
  you, from whom you expect), and the algorithm (pin it — never trust the token's own
  `alg`, or you enable the classic "`alg: none`"/algorithm-confusion attacks).
- **Trade-off:** JWTs can't be easily revoked before expiry (they're self-contained), so
  you keep access tokens short-lived and use refresh tokens.

## 2. In TrialReads

Supabase Auth issues the tokens; the FastAPI backend **verifies** them
(`backend/app/auth.py`). Supabase Auth handles the sensitive parts I should *not*
hand-roll: password hashing, email confirmation, OAuth (there's an
`app/auth/callback/page.tsx` OAuth callback route), and refresh-token rotation.

**Key discovery — this project uses ES256 (asymmetric).** During Phase 1 I assumed
HS256 and it rejected real tokens; inspecting a live token showed `"alg": "ES256"` with
a `kid`. So verification uses **JWKS**:

- `PyJWKClient(_JWKS_URL, cache_keys=True)` points at
  `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` and **caches** the fetched public keys
  (`auth.py:28-31`).
- `_decode()` reads the token's `alg`; for ES256/RS256 it fetches the signing key by
  `kid` from JWKS and verifies; it also keeps an **HS256 fallback** against the legacy
  shared secret (`auth.py:44-62`).
- It pins the allowed algorithms (`["ES256", "RS256"]`) and checks the audience
  (`aud = "authenticated"`) — so a token for a different audience or signed with an
  unexpected algorithm is rejected.

**The dependency.** `get_current_user_id` is a FastAPI dependency: no/blank token → 401;
expired → 401 "Token expired"; bad signature/claims → 401 "Invalid token"; JWKS/key
errors → 401. On success it extracts `sub` (the user UUID) and returns it — and also
stamps it onto the current **OpenTelemetry span** as `app.user_id` (a span attribute,
never a metric label — section 09) (`auth.py:65-93`).

**Why this pairs with everything else:** the verified `sub` is the single source of
identity used everywhere — CRUD scoping (`WHERE user_id = :me`), RLS claims for
text-to-SQL, and rate-limit keys. Identity flows from one cryptographically-verified
place.

## 3. Gaps & upgrades to industry standard

- **HS256 fallback is a small attack surface.** Accepting HS256-signed tokens (against
  the shared secret) alongside ES256 exists for migration convenience. Since the project
  is fully on ES256, dropping the HS256 branch would remove any chance of an
  algorithm-confusion mistake. (The secret is backend-only, so risk is low — but "remove
  what you don't need" is the stricter posture.)
- **JWKS cache has no explicit refresh/negative-cache policy in view.** `PyJWKClient`
  caches keys; production wants a bounded TTL and a strategy for "unknown `kid`" (fetch
  once, then fail closed) so a key rotation is picked up promptly but a bad `kid` can't
  cause a fetch storm.
- **No token revocation / logout-everywhere.** JWTs are valid until `exp`. For
  "sign out all devices" or instant ban you need a denylist (jti) checked per request, or
  short access tokens + refresh rotation (Supabase does the latter).
- **No explicit `iss` check** in the decode call (aud is checked). Verifying the issuer
  is the Supabase project too is a cheap hardening.
- **Clock-skew tolerance** isn't configured; PyJWT's default is 0s. A small `leeway`
  avoids false "expired" rejections across slightly-skewed clocks.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. What's in a JWT and how do you verify one?**
A: Three parts — header (alg + kid), payload (claims like `sub`, `exp`, `aud`), and a
signature. To verify I recompute/validate the signature with the right key, then check
`exp` (not expired), `aud` (meant for me), and pin the algorithm. Only then do I trust
`sub` as the user id. My code does exactly this via PyJWT, rejecting anything that fails
with a 401.

**Q2. HS256 vs ES256 — which does your app use and why does it matter?**
A: ES256 — asymmetric. Supabase signs with a private key it alone holds; my backend
verifies with the public key from the JWKS endpoint. That matters because with HS256's
shared secret, anything that can verify can also forge tokens; with ES256 my resource
server can verify without ever being able to mint a token. I discovered this the hard
way — my initial HS256 verifier rejected real tokens until I inspected the header and
saw `alg: ES256`.

**Q3. What is JWKS and what problem does it solve?**
A: A JSON Web Key Set is the public keys published at a well-known URL, each with a
`kid`. The token header names the `kid` that signed it; my verifier fetches that key and
verifies. It solves key rotation — Supabase can rotate signing keys and publish new
public keys, and my backend picks them up from JWKS without a redeploy. I cache the keys
so it's not a fetch per request.

**Q4. Why is JWT auth a good fit for a stateless, horizontally-scaled backend?**
A: Because verification needs only the token and a public key — no session lookup, no
shared session store. Any instance can authenticate any request independently, which is
exactly what lets me run N backend instances behind a load balancer without sticky
sessions.

**Q5. What's the "alg: none" / algorithm-confusion attack and how do you prevent it?**
A: If a verifier trusts the token's own `alg` field, an attacker can set `alg: none`
(no signature) or swap an RS256 public key into an HS256 verification (using the public
key as the HMAC secret). Prevention: never trust the token's `alg` — pin an allowlist
server-side. I pin `["ES256","RS256"]` (with a controlled HS256 branch) and pass explicit
`algorithms=` to PyJWT.

**Q6. JWTs can't be revoked before expiry. How do you handle logout or a banned user?**
A: Keep access tokens short-lived and rotate refresh tokens (Supabase does this), so a
stolen token dies quickly. For instant revocation — sign-out-everywhere or a ban — add a
server-side denylist keyed by the token's `jti`, checked per request; it reintroduces a
tiny bit of state but only for revoked tokens. It's the classic statelessness-vs-instant-
revocation trade-off.

**Q7. Where does `user_id` come from in your app, and why never from the request body?**
A: From the verified JWT's `sub`, surfaced by the `get_current_user_id` dependency.
Taking it from the body would be a confused-deputy/IDOR hole — a caller could claim any
id. Because it comes from a cryptographically verified token, everything downstream (CRUD
scoping, RLS claims, rate-limit keys) can trust it.

**Q8. Walk me through what happens on an expired token.**
A: PyJWT raises `ExpiredSignatureError` during `decode` (it checks `exp`), my dependency
catches it and returns 401 with `WWW-Authenticate: Bearer` and detail "Token expired."
The frontend's Supabase client then uses the refresh token to get a new access token and
retries — the user never notices.

**Q9. How would you harden this verification further?**
A: Drop the HS256 fallback now that we're fully ES256 (removes any algorithm-confusion
foothold), add an explicit `iss` check, add a small clock-skew `leeway`, set a bounded
JWKS cache TTL with fail-closed handling of unknown `kid`, and add revocation via a `jti`
denylist for the ban case.

**Q10. Should you verify JWTs yourself or use a gateway/library?**
A: For a single service, verifying in a small, well-tested dependency (PyJWT + JWKS) is
fine and keeps auth close to the code. At scale, an API gateway or service mesh verifying
once at the edge avoids every service re-implementing it and centralizes rotation and
policy. The key rule either way: never hand-roll the *crypto* — use a vetted library.

---

### Follow-ups interviewers love here
- "Where do you store the token on the client?" → Supabase client keeps the session; the
  security trade-off is httpOnly cookie (XSS-safe, CSRF-exposed) vs. JS-readable storage
  (CSRF-safe, XSS-exposed).
- "What claims do you check?" → signature, `exp`, `aud`; you'd add `iss`.
- "Access vs refresh token?" → short-lived access (verified per request), long-lived
  refresh (exchanged for new access tokens, rotated on use).
