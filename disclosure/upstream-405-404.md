# Draft disclosure to David — two error-envelope gaps

**Status: DRAFT — not sent.** Ready to paste into a GitHub issue on
`davidondrej/skills` or send as a DM. Covers only the two findings that are
outright contract violations (`FINDINGS.md` #1 and #2); the spec-enum and nits
(#3, #4) are deliberately left out to keep this actionable.

Everything below is from public surfaces + `$0` unauthenticated probes against
production `deepapi.co` on 2026-07-16 (`skillVersion c371bb41c769`). No key sent,
nothing billed. Authenticated / billable / intrusive classes (IDOR, rate-limit,
billing, policy bypass) were **not** tested and aren't claimed clean.

---

## Subject

Error-envelope guarantee has two holes: `405` (wrong method) and unmatched
`/v1/*` return no `error.code`

## Body

Hey David — I mapped the DeepAPI contract from the public skill files and probed
production unauthenticated (no key, nothing billed). *(Probed 2026-07-16 at
`skillVersion c371bb41c769` from `/v1/health`; both one-liners below still
reproduce as of now.)* The error design is genuinely good: every response carries
`error.code` / `retryable` / `retryAfterSecs` / `hint`, `invalid_request` ships a
`fix` an agent can rebuild from, failed calls report `debitMicrousd: null`, and
the scoped-key model is real. An agent can branch on `error.code` and
self-correct — which is exactly why these two gaps sting: they're the cases where
that machinery gets nothing back.

**1. Wrong HTTP method → bare `405`, empty body, no `error.code`, no `Allow`.**

```console
$ curl -i https://deepapi.co/v1/search/web        # GET on a POST-only route
HTTP/2 405
x-matched-path: /v1/search/web
# …no Allow header, no content-type, empty body
```

The route matches (that `x-matched-path` confirms it) — so it's the handler
rejecting the method with a bare `405`, not an unregistered route. Two things
break at once:

- The envelope guarantee (`llms.txt`: *"Every failed response carries
  `error.code` …"*) — no `code`, so an agent can't branch or self-correct.
- RFC 9110 §15.5.6 — a `405` **MUST** generate an `Allow` header; this one has none.

A `GET`-instead-of-`POST` slip is one of the most common agent mistakes, and it's
the failure the "branch on `error.code`" design exists to catch. Right now the
agent gets an empty body and no signal.

*Fix:* return the standard envelope on `405` (e.g. `method_not_allowed` /
`invalid_request` with a `hint`) and set `Allow: POST`.

**2. Unmatched `/v1/*` path → HTML 404, not the envelope.**

```console
$ curl -i https://deepapi.co/v1/nope
HTTP/2 404
content-type: text/html; charset=utf-8
x-matched-path: /404                     # fell through to the platform 404 route
<!DOCTYPE html><html …>        # the Next.js/Vercel 404 page, not the envelope
```

A `/v1/*` path that matches no route *shape* (a hallucinated endpoint, or a
misspelled segment like `scrpe`) falls through to the platform HTML 404. The
contract already defines the right codes for this — `unknown_capability` and
`resource_not_found`, both `404` — they just aren't reached on an unmatched path.

The boundary is clean, for what it's worth: an unknown **param value** is handled
correctly because it still matches the dynamic route —

```console
$ curl -i https://deepapi.co/v1/scrape/tiktok
HTTP/2 405
x-matched-path: /v1/scrape/[target]     # matched [target]; a POST returns the envelope
```

So the gap is specifically unmatched route *structures*, not unknown targets.

*Fix:* a `/v1/*` catch-all that returns the envelope with `unknown_capability`
instead of letting the request reach the site's 404 page.

Both are reproducible with the one-line `curl`s above. Happy to send the full
recon (endpoint parity, pricing parity, header/CORS checks all came back clean)
if useful. Nice work on the contract overall.

---

## Not included here (on purpose)

- `openapi.json` `PublicError.code` is a bare `string` — no `enum` of the 52
  codes, so a generated SDK loses the code table. Real, but a docs/spec polish,
  not a runtime break. (`FINDINGS.md` #3.)
- Nits: frozen `info.version 0.1.0`, validation order (`missing_idempotency_key`
  reported before `invalid_api_key`), `request_failed` vs `*_request_failed`
  naming. (`FINDINGS.md` #4.)
