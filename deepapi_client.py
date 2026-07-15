#!/usr/bin/env python3
"""Minimal DeepAPI client implementing the SKILL.md contract.

Rules encoded from skills/research-and-web/deepapi/SKILL.md:
- Bearer auth from DEEPAPI_API_KEY (never printed)
- Base URL from DEEPAPI_API_BASE_URL (default https://deepapi.co)
- Unique Idempotency-Key on every POST, stable across same-key retries
- Explicit maxCostUsd cap on every scrape/research/search/image call
- Poll next.path while status == running; honor error.retryable/retryAfterSecs
- Retry key reuse per the error table: same key by default, NEW key for the
  codes the table marks that way (upstream_rate_limited, request_failed)
- invalid_request self-correction via error.fix (rebuild body, retry new key)
- Bounded retries (MAX_ATTEMPTS); failed calls are free (debitMicrousd: null)
- 402 insufficient_credits -> stop and tell the user to top up

Usage:
  python3 deepapi_client.py website https://example.com
  python3 deepapi_client.py yt-transcript https://youtube.com/watch?v=...
  python3 deepapi_client.py search "node lts version"
  python3 deepapi_client.py research "question here"
  python3 deepapi_client.py github octocat
  python3 deepapi_client.py linkedin williamhgates
  python3 deepapi_client.py twitter nasa
  python3 deepapi_client.py status <requestId>
"""
import json, os, sys, time, uuid, urllib.request, urllib.error

BASE = os.environ.get("DEEPAPI_API_BASE_URL", "https://deepapi.co").rstrip("/")
KEY = os.environ.get("DEEPAPI_API_KEY")
MAX_ATTEMPTS = 4                      # bound every retry loop

# default cost caps per endpoint, straight from SKILL.md
CAPS = {
    "/v1/scrape/website": "1.00", "/v1/scrape/linkedin/profile": "0.05",
    "/v1/scrape/github/profile": "0.03", "/v1/scrape/twitter/search": "0.03",
    "/v1/scrape/youtube/transcript": "0.05", "/v1/search/web": "0.05",
    "/v1/research/deep": "0.10", "/v1/generate/image": "0.20",
}

# The error table is 51 codes but only ~6 behaviours. The response itself is
# authoritative — error.retryable says whether, error.retryAfterSecs says how
# long — so the client trusts those fields and only hardcodes the short list
# the table marks "retry with a NEW Idempotency-Key".
NEW_KEY_ON_RETRY = {"upstream_rate_limited", "request_failed"}


def _decide(resp, http):
    """Collapse any failed envelope into (action, detail). Actions:
    stop | self_correct | retry_same | retry_new."""
    err = resp.get("error", {}) or {}
    code = err.get("code", "")
    if code == "insufficient_credits":
        return "stop", "Insufficient credits — top up at https://deepapi.co/credits, then retry."
    if code == "invalid_request" and isinstance(err.get("fix"), dict):
        return "self_correct", err["fix"]
    if err.get("retryable"):
        action = "retry_new" if code in NEW_KEY_ON_RETRY else "retry_same"
        return action, err.get("retryAfterSecs", 5)
    hint = err.get("hint", "")
    return "stop", f"HTTP {http} {code}: {err.get('message', '')}" + (f" — {hint}" if hint else "")


def call(method, path, body=None, idem=None, attempt=1):
    if not KEY:
        sys.exit("DEEPAPI_API_KEY not set (get one at https://deepapi.co). "
                 "Tip: store it in the login keychain and export via `security find-generic-password -w`.")
    if method == "POST":
        idem = idem or str(uuid.uuid4())          # kept stable across same-key retries
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Authorization", f"Bearer {KEY}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
        req.add_header("Idempotency-Key", idem)
    try:
        with urllib.request.urlopen(req, data) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            resp = json.loads(e.read().decode(errors="replace"))
        except json.JSONDecodeError:
            sys.exit(f"HTTP {e.code}: non-JSON error body")
        code = resp.get("error", {}).get("code", "")
        action, detail = _decide(resp, e.code)      # failed calls are free: debitMicrousd is null

        if action == "stop":
            sys.exit(detail)
        if attempt >= MAX_ATTEMPTS:
            sys.exit(f"gave up after {MAX_ATTEMPTS} attempts on {path} ({code})")

        if action == "self_correct":
            fix = detail
            if isinstance(body, dict) and isinstance(fix.get("exampleBody"), dict):
                fixed = {**fix["exampleBody"], **body}   # keep our intent, fill the required shape
                print(f"invalid_request on `{resp['error'].get('field')}` — self-correcting "
                      f"from error.fix, new key (attempt {attempt}/{MAX_ATTEMPTS})", file=sys.stderr)
                return call(method, path, fixed, idem=None, attempt=attempt + 1)
            sys.exit(f"invalid_request: {resp['error'].get('message')} "
                     f"(schema: {json.dumps(fix)[:400]})")

        reuse = action == "retry_same"              # else retry_new -> fresh idempotency key
        print(f"{code}: retryable, waiting {detail}s "
              f"(attempt {attempt}/{MAX_ATTEMPTS}, {'same' if reuse else 'new'} key)", file=sys.stderr)
        time.sleep(detail)
        return call(method, path, body, idem=idem if reuse else None, attempt=attempt + 1)


def run(path, body):
    body.setdefault("maxCostUsd", CAPS.get(path, "0.10"))
    body.setdefault("waitForFinishSecs", 60)
    resp = call("POST", path, body)
    while resp.get("status") == "running":
        nxt = resp.get("next", {})
        time.sleep(nxt.get("afterSecs", 5))
        resp = call(nxt.get("method", "GET"), nxt.get("path", f"/v1/requests/{resp['requestId']}"))
    if resp.get("status") == "failed":              # async logical failure — also free
        err = resp.get("error", {}) or {}
        sys.exit(f"request {resp.get('requestId')} failed: {err.get('code')} — {err.get('message', '')}")
    print(json.dumps({k: resp.get(k) for k in ("requestId", "status", "output")}, indent=2))
    return resp


CMDS = {
    "website":       lambda a: run("/v1/scrape/website", {"urls": [a], "maxPages": 1}),
    "yt-transcript": lambda a: run("/v1/scrape/youtube/transcript", {"url": a}),
    "search":        lambda a: run("/v1/search/web", {"query": a, "maxResults": 5}),
    "research":      lambda a: run("/v1/research/deep", {"query": a}),
    "github":        lambda a: run("/v1/scrape/github/profile", {"usernames": [a]}),
    "linkedin":      lambda a: run("/v1/scrape/linkedin/profile", {"profiles": [a]}),
    "twitter":       lambda a: run("/v1/scrape/twitter/search", {"handles": [a], "maxItems": 5, "sort": "latest"}),
    "status":        lambda a: print(json.dumps(call("GET", f"/v1/requests/{a}"), indent=2)),
}

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in CMDS:
        sys.exit(__doc__)
    CMDS[sys.argv[1]](" ".join(sys.argv[2:]))
