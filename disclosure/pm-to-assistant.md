# PM to David's assistant — copy/paste

Short DM version of [`upstream-405-404.md`](upstream-405-404.md), sized for a
direct message to David's assistant to forward. Same two findings, same
`$0`-unauthenticated evidence. Fill in the name and send as-is.

---

Hi [name] — could you pass this to David when you get a sec?

I've been mapping the DeepAPI contract from the public `davidondrej/skills`
files and probing production **unauthenticated** — no key, nothing billed ($0).
The error design is genuinely good: every response carries `error.code` /
`retryable` / `retryAfterSecs` / `hint`, `invalid_request` ships a `fix` an agent
can rebuild from, and the scoped-key model is real. Which is exactly why two
small gaps stand out — they're the cases where that self-correction machinery
gets nothing back:

**1. Wrong HTTP method → bare `405`, empty body, no `error.code`, no `Allow`.**
```
curl -i https://deepapi.co/v1/search/web        # GET on a POST-only route
→ HTTP/2 405, x-matched-path: /v1/search/web, no Allow header, empty body
```
Breaks the "every failed response carries `error.code`" guarantee, and also
RFC 9110 §15.5.6 (a `405` must send `Allow`). A GET-instead-of-POST slip is a
common agent mistake and it gets no signal back. Fix: return the normal envelope
+ `Allow: POST`.

**2. Unmatched `/v1/*` path → HTML 404, not the JSON envelope.**
```
curl -i https://deepapi.co/v1/nope
→ HTTP/2 404, content-type: text/html    (the Next/Vercel 404 page)
```
A hallucinated or misspelled route falls through to the platform 404 instead of
returning `unknown_capability`. (Unknown *param* values like `/v1/scrape/tiktok`
are fine — they still match the dynamic route.) Fix: a `/v1/*` catch-all that
returns the envelope.

Both reproduce with the one-liners above, all from public surfaces — nothing
authenticated, nothing billed. Full recon (repro, endpoint + pricing parity, and
a checked-and-clean list of everything that came back fine):
https://github.com/ANcpLua/deepapi-recon — the two findings above are written up
in [`FINDINGS.md`](https://github.com/ANcpLua/deepapi-recon/blob/main/FINDINGS.md).
Contract looks great overall — just flagging these two.

Thanks!
