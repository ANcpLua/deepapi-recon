#!/usr/bin/env python3
"""Minimal DeepAPI client implementing the SKILL.md contract.

Rules encoded from skills/research-and-web/deepapi/SKILL.md:
- Bearer auth from DEEPAPI_API_KEY (never printed)
- Base URL from DEEPAPI_API_BASE_URL (default https://deepapi.co)
- Unique Idempotency-Key on every POST
- Explicit maxCostUsd cap on every scrape/research/search/image call
- Poll next.path while status == running; honor error.retryable/retryAfterSecs
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

# default cost caps per endpoint, straight from SKILL.md
CAPS = {
    "/v1/scrape/website": "1.00", "/v1/scrape/linkedin/profile": "0.05",
    "/v1/scrape/github/profile": "0.03", "/v1/scrape/twitter/search": "0.03",
    "/v1/scrape/youtube/transcript": "0.05", "/v1/search/web": "0.05",
    "/v1/research/deep": "0.10", "/v1/generate/image": "0.20",
}

def call(method, path, body=None, idem=None):
    if not KEY:
        sys.exit("DEEPAPI_API_KEY not set (get one at https://deepapi.co). "
                 "Tip: store it in the login keychain and export via `security find-generic-password -w`.")
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Authorization", f"Bearer {KEY}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
        req.add_header("Idempotency-Key", idem or str(uuid.uuid4()))
    try:
        with urllib.request.urlopen(req, data) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        payload = e.read().decode(errors="replace")
        if e.code == 402:
            sys.exit("Insufficient credits — top up at https://deepapi.co/credits, then retry.")
        try:
            err = json.loads(payload).get("error", {})
            if err.get("retryable"):
                wait = err.get("retryAfterSecs", 5)
                print(f"retryable error, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                return call(method, path, body, idem)
        except json.JSONDecodeError:
            pass
        sys.exit(f"HTTP {e.code}: {payload[:500]}")

def run(path, body):
    body.setdefault("maxCostUsd", CAPS.get(path, "0.10"))
    body.setdefault("waitForFinishSecs", 60)
    resp = call("POST", path, body)
    while resp.get("status") == "running":
        nxt = resp.get("next", {})
        time.sleep(nxt.get("afterSecs", 5))
        resp = call(nxt.get("method", "GET"), nxt.get("path", f"/v1/requests/{resp['requestId']}"))
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
