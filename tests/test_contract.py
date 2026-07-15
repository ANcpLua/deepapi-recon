#!/usr/bin/env python3
"""Three runnable tests, one per elegance gap in the naive client.

The theme: **the happy path is the mistake.** Each scenario is the kind of error
DeepAPI actually returns; the naive client's straightforward reaction is wrong,
and the fixed client honors the SKILL.md contract.

Run it two ways:
    python3 tests/test_contract.py     # prints the naive-vs-fixed matrix, then asserts
    python3 -m unittest -v             # plain unittest
"""
import os, sys, contextlib, warnings, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                       # runnable via `python3 tests/...` or `-m unittest`
import fake_deepapi as fk

warnings.simplefilter("ignore", ResourceWarning)
NAIVE = fk.load_client(os.path.join(HERE, "_naive_client.py"), "naive")
FIXED = fk.load_client(os.path.join(HERE, "..", "deepapi_client.py"), "fixed")

# --- scripted DeepAPI error envelopes (shape straight from the SKILL.md table) ---
def envelope(code, retryable, **extra):
    return {"requestId": None, "status": "failed", "debitMicrousd": None,
            "error": {"code": code, "retryable": retryable, "retryAfterSecs": 0, **extra}}

RATE_LIMIT   = envelope("rate_limit_exceeded", True)                 # table: retry, SAME key
SERVER_FAIL  = envelope("scrape_request_failed", True)              # table: retry, SAME key (persistent here)
INVALID      = envelope("invalid_request", False, field="query",
                        message="query is required",
                        fix={"requiredFields": ["query"],
                             "exampleBody": {"query": "example", "maxResults": 5}})
OK           = {"requestId": "r1", "status": "succeeded", "output": {"ok": True}}


def drive(client, script, path="/v1/search/web", body=None):
    """Run one request through a client against a scripted fake; return the fake."""
    fake = fk.FakeDeepAPI(script)
    fk.install(fake)
    with open(os.devnull, "w") as dn, contextlib.redirect_stdout(dn), contextlib.redirect_stderr(dn):
        try:
            client.run(path, dict(body or {"query": "x"}))
        except (SystemExit, RecursionError) as e:
            fake.exit = e
    return fake


# --- the three checks. each returns True when the client is CORRECT. ---
def check_idempotency(client):
    """Gap 1: a same-key retryable error must retry with the SAME Idempotency-Key."""
    f = drive(client, [("err", 429, RATE_LIMIT), ("ok", OK)])
    return f.n == 2 and f.keys[0] is not None and f.keys[0] == f.keys[1]

def check_bounded(client):
    """Gap 2: a persistently-retryable error must stop after a bounded # of attempts."""
    lim = sys.getrecursionlimit(); sys.setrecursionlimit(200)
    try:
        f = drive(client, [("err", 502, SERVER_FAIL)])          # never succeeds
    finally:
        sys.setrecursionlimit(lim)
    return f.n <= 8 and isinstance(getattr(f, "exit", None), SystemExit)

def check_self_correct(client):
    """Gap 3: invalid_request + error.fix must be rebuilt and retried, not dropped."""
    f = drive(client, [("err", 400, INVALID), ("ok", OK)])
    return f.n == 2 and f.calls[-1]["body"].get("maxResults") == 5   # example fields merged in


CHECKS = [
    ("1  same-key idempotency on retry", check_idempotency,
     "naive mints a fresh key each retry → double-execute risk"),
    ("2  bounded retries (no infinite loop)", check_bounded,
     "naive recurses forever on a persistent retryable error"),
    ("3  error.fix self-correction", check_self_correct,
     "naive drops error.fix and gives up on invalid_request"),
]


class Contract(unittest.TestCase):
    def test_fixed_honors_contract(self):
        for label, fn, _ in CHECKS:
            with self.subTest(gap=label):
                self.assertTrue(fn(FIXED), f"fixed client should pass: {label}")

    def test_naive_exhibits_the_bug(self):
        for label, fn, _ in CHECKS:
            with self.subTest(gap=label):
                self.assertFalse(fn(NAIVE), f"naive client should fail: {label}")


def matrix():
    ok = "\033[32m✓\033[0m"; bad = "\033[31m✗\033[0m"
    print("\n  the happy path is the mistake\n")
    print(f"  {'gap':<38}{'naive':^8}{'fixed':^8}")
    print(f"  {'-'*54}")
    for label, fn, why in CHECKS:
        n = ok if fn(NAIVE) else bad
        x = ok if fn(FIXED) else bad
        print(f"  {label:<38}{n:^17}{x:^17}")
        print(f"    \033[2m{why}\033[0m")
    print()


if __name__ == "__main__":
    matrix()
    unittest.main(argv=[sys.argv[0], "-v"], exit=False)
