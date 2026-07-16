# DeepAPI — findings that need fixing

Issues in **DeepAPI itself** (not in this repo, and not in the naive client the
[contract audit](contract_audit.py) grades). Everything here is evidenced: each
finding has a one-line `curl` you can rerun. Nothing is inferred.

**Method.** Public contract surfaces (`llms.txt`, `openapi.json`, `docs/*.md`,
the installable `SKILL.md`) plus **$0 unauthenticated** probes against
production `deepapi.co`. No key sent, nothing billed.
**Probed:** 2026-07-16, `skillVersion c371bb41c769`.

The bar after a long "don't manufacture blame" review: a finding ships only if a
command reproduces it and it contradicts DeepAPI's own documented contract or a
standard. Six candidates were **dropped** for lack of evidence — see
[Checked and clean](#checked-and-clean).

| # | Finding | Severity | Rule it breaks |
|---|---|---|---|
| 1 | Wrong HTTP method → bare `405`, empty body, no `error.code`, no `Allow` | **Medium** | `llms.txt` envelope guarantee + RFC 9110 §15.5.6 |
| 2 | Unmatched `/v1/*` path → HTML 404, not the JSON envelope | Low–Med | `llms.txt` envelope guarantee |
| 3 | `openapi.json` doesn't enumerate the error-code vocabulary | Low | spec ↔ docs parity |
| 4 | Three nits (spec version, validation order, `request_failed` naming) | Low / nit | — |

---

## 1. Wrong HTTP method → bare `405`, empty body, no `error.code` — Medium

The contract's centerpiece guarantee (`llms.txt:1210`):

> Every failed response carries `error.code`, `error.retryable`,
> `error.retryAfterSecs`, and `error.hint`.

It does not hold for a method mismatch:

```console
$ curl -i https://deepapi.co/v1/search/web        # GET on a POST-only route
HTTP/2 405
x-matched-path: /v1/search/web
# …no Allow header, no content-type, empty body
```

The route *matches* (`x-matched-path` confirms it), so this isn't a routing
miss — the handler rejects the method with a bare `405`. That breaks two things
at once:

- **DeepAPI's own envelope contract** — no `error.code`, so an agent can't
  branch or self-correct.
- **RFC 9110 §15.5.6** — a `405` response **MUST** generate an `Allow` header;
  this one doesn't.

**Why it matters.** A `GET`-instead-of-`POST` slip is one of the most common
agent mistakes, and it's exactly the failure the "branch on `error.code` and
self-correct" design exists to catch. Here the agent gets an empty body and no
signal.

**Fix.** Return the standard envelope on `405` (e.g. a `method_not_allowed` /
`invalid_request` code with a `hint`), and set `Allow: POST`.

---

## 2. Unmatched `/v1/*` path → HTML 404, not the JSON envelope — Low–Med

```console
$ curl -i https://deepapi.co/v1/nope
HTTP/2 404
content-type: text/html; charset=utf-8
x-matched-path: /404                     # fell through to the platform 404 route
<!DOCTYPE html><html …>   # the Next.js/Vercel 404 page, not the envelope
```

A `/v1/*` path that matches no route *shape* (a hallucinated endpoint, or a
misspelled static segment like `scrpe`) falls through to the platform's HTML
404. The contract even defines the right codes for this — `unknown_capability`
and `resource_not_found`, both `404` — but they're never reached on an unmatched
path.

Note the boundary: an unknown **param value** is handled correctly, because it
still matches the dynamic route —

```console
$ curl -i https://deepapi.co/v1/scrape/tiktok
HTTP/2 405
x-matched-path: /v1/scrape/[target]      # matched [target]; POST would return the envelope
```

So the gap is specifically unmatched route *structures*, not unknown targets.

**Fix.** Add a `/v1/*` catch-all that returns the envelope with
`unknown_capability` instead of letting the request reach the site's 404.

---

## 3. `openapi.json` doesn't enumerate the error-code vocabulary — Low

`PublicError.code` is a bare string, and every operation documents its error
responses only as `4XX` / `5XX` ranges:

```console
$ curl -s https://deepapi.co/openapi.json | python3 -c '
import sys,json; s=json.load(sys.stdin)
print("code schema:", s["components"]["schemas"]["PublicError"]["properties"]["code"])
print("website error responses:", list(s["paths"]["/v1/scrape/website"]["post"]["responses"]))'
code schema: {'type': 'string'}                    # ← no enum
website error responses: ['201', '202', '4XX', '5XX']
```

**45 of the 52** error codes documented in the `llms.txt` table appear nowhere
in the spec. An SDK generated from `openapi.json` therefore loses the entire
code table and the code→HTTP mapping.

**Credit where due:** the *envelope* is modeled well — `PublicError` **requires**
`retryable`, `retryAfterSecs`, `requiredScope`, and `hint`, and models
`fix` → `PublicErrorFix` (`bodySchema` / `requiredFields` / `exampleBody`). So
generic retry and `error.fix` self-correction still generate correctly from the
spec; only the specific-code layer is missing.

**Fix.** Add an `enum` of the 52 codes to `PublicError.code`; optionally list the
codes each operation can actually return, and swap the `4XX`/`5XX` buckets for
the concrete statuses the table already assigns.

---

## 4. Nits — Low

- **Spec version is frozen.** `openapi.json` `info.version` is a static `0.1.0`
  with no `x-skillVersion`, while every live and doc surface reports a
  `skillVersion` that bumps often (`c371bb41c769` at probe time). Tooling that
  pins or diffs the spec by its version can't detect drift the way the
  contract's own drift-detection story promises.

- **Validation order.** A present-but-invalid bearer is validated *after* the
  idempotency-key check, so a bad key with no idempotency key reports the wrong
  problem first:

  ```console
  $ curl -s -X POST https://deepapi.co/v1/search/web \
      -H 'authorization: Bearer nope' -H 'content-type: application/json' \
      -d '{"query":"x"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["error"]["code"])'
  missing_idempotency_key            # not invalid_api_key → agent fixes the wrong thing, then retries
  ```

  (No auth header at all correctly returns `missing_api_key`.)

- **`request_failed` vs `*_request_failed`.** `request_failed` says retry with a
  **new** key; `scrape_request_failed`, `email_send_failed`, … say retry with the
  **same** key. The distinction is coherent (the provider run failed vs. the
  server glitched while handling the request), but the near-identical names
  invite conflation. One clarifying sentence in the error table would remove the
  ambiguity.

---

## Checked and clean

Verified with evidence and found **no** issue — listed so the sweep reads as a
sweep, not a cherry-pick. Six weaker candidates died here.

| Checked | Result |
|---|---|
| Endpoint parity `openapi.json` ↔ `llms.txt` | **53 ≡ 53**, zero diff |
| Default cost caps `llms.txt` ↔ `pricing.md` | **0 mismatches / 28** endpoints |
| `skillVersion` across all surfaces at one instant | consistent (`c371bb41c769`) |
| Least-privilege keys | **real** — per-endpoint `Scope:`, `missing_scope` ("ask for a key *with that scope*"), per-key spend limits. The "unscoped key" idea is dead. |
| Security headers on responses | HSTS, `nosniff`, `X-Frame-Options: DENY`, `permissions-policy`, `referrer-policy` all present |
| CORS | closed — preflight `204`, no `Access-Control-Allow-Origin` echoed (correct for a bearer API) |
| Every documented docs URL | all resolve `200` (`llms.txt`, `openapi.json`, `docs/*.md`, `deepapi-skill/SKILL.md`) |
| Error envelope in the spec | `retryable` / `retryAfterSecs` / `requiredScope` / `fix` all modeled and required |
| `error.fix` self-correction & dry-run pre-flight | fully specified |

---

## Scope — what this pass did NOT test

Not a claim that DeepAPI is flawless. These need an authenticated key, would
incur billing, and would be intrusive testing on someone else's production, so
they were **out of scope** — not cleared:

- Cross-key IDOR on `GET /v1/memory/{path}` and `GET /v1/requests/{requestId}`
  (both scoped "same key that created it" — untested).
- Rate-limit robustness (`rate_limit_exceeded` also covers failed-auth attempts).
- Email / X / deploy policy-bypass surfaces.
- Billing correctness (`debitMicrousd`, spend-cap enforcement, `dryRun` estimates).

The two findings worth acting on first are **#1** and **#2** — the only two that
are outright contract violations an agent will hit in normal use.
