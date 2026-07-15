"""Shared contract-audit logic.

An in-process fake DeepAPI, the naive + fixed clients loaded side by side, and
the three checks that pin the SKILL.md retry/idempotency contract. Each gap
carries the metadata the SARIF auditor needs (rule id, severity, remediation,
and the source anchor that locates the offending line). Imported by both the
unittest suite (test_contract.py) and the auditor (contract_audit.py).
"""
import os, sys, contextlib, warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fake_deepapi as fk

warnings.simplefilter("ignore", ResourceWarning)

NAIVE_PATH = os.path.join(HERE, "_naive_client.py")
FIXED_PATH = os.path.normpath(os.path.join(HERE, "..", "deepapi_client.py"))
NAIVE = fk.load_client(NAIVE_PATH, "naive")
FIXED = fk.load_client(FIXED_PATH, "fixed")


def envelope(code, retryable, **extra):
    return {"requestId": None, "status": "failed", "debitMicrousd": None,
            "error": {"code": code, "retryable": retryable, "retryAfterSecs": 0, **extra}}

RATE_LIMIT  = envelope("rate_limit_exceeded", True)                 # table: retry, SAME key
SERVER_FAIL = envelope("scrape_request_failed", True)              # table: retry, SAME key
INVALID     = envelope("invalid_request", False, field="query", message="query is required",
                       fix={"requiredFields": ["query"], "exampleBody": {"query": "example", "maxResults": 5}})
OK          = {"requestId": "r1", "status": "succeeded", "output": {"ok": True}}


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


def check_idempotency(client):
    """A same-key retryable error must retry with the SAME Idempotency-Key."""
    f = drive(client, [("err", 429, RATE_LIMIT), ("ok", OK)])
    return f.n == 2 and f.keys[0] is not None and f.keys[0] == f.keys[1]

def check_bounded(client):
    """A persistently-retryable error must stop after a bounded # of attempts."""
    lim = sys.getrecursionlimit(); sys.setrecursionlimit(200)
    try:
        f = drive(client, [("err", 502, SERVER_FAIL)])
    finally:
        sys.setrecursionlimit(lim)
    return f.n <= 8 and isinstance(getattr(f, "exit", None), SystemExit)

def check_self_correct(client):
    """invalid_request + error.fix must be rebuilt and retried, not dropped."""
    f = drive(client, [("err", 400, INVALID), ("ok", OK)])
    return f.n == 2 and f.calls[-1]["body"].get("maxResults") == 5


# Each gap: the check, plus everything the SARIF rule/result needs. `anchor` is a
# substring that locates the offending line in a client that FAILS the check.
GAPS = [
    {
        "id": "deepapi/idempotency-key-not-reused",
        "title": "Retry mints a new Idempotency-Key, breaking same-key idempotency",
        "severity": "high",
        "check": check_idempotency,
        "anchor": 'add_header("Idempotency-Key"',
        "label": "same-key idempotency on retry",
        "description": (
            "On a retryable error the client generates a fresh Idempotency-Key instead of "
            "reusing it. For the codes the DeepAPI error table marks \"retry with the same key\" "
            "(rate_limit_exceeded, idempotency_conflict, every *_request_failed), the retry is "
            "treated as a brand-new operation — risking duplicate execution and double billing."
        ),
        "recommendation": (
            "Generate the Idempotency-Key once and reuse it across retries; only rotate it for "
            "upstream_rate_limited / request_failed, which the table marks new-key."
        ),
    },
    {
        "id": "deepapi/unbounded-retry-recursion",
        "title": "Unbounded retry recursion on persistent retryable errors",
        "severity": "high",
        "check": check_bounded,
        "anchor": "return call(method, path, body, idem)",
        "label": "bounded retries (no infinite loop)",
        "description": (
            "The retry path recurses with no attempt bound. A persistently-retryable error "
            "(e.g. a sustained 502 *_request_failed) recurses until the stack overflows — a "
            "self-inflicted denial of service."
        ),
        "recommendation": "Bound retries with a max-attempts counter and give up with a clear error.",
    },
    {
        "id": "deepapi/error-fix-ignored",
        "title": "invalid_request self-correction (error.fix) is ignored",
        "severity": "medium",
        "check": check_self_correct,
        "anchor": 'sys.exit(f"HTTP {e.code}: {payload',
        "label": "error.fix self-correction",
        "description": (
            "invalid_request responses carry error.fix (bodySchema, requiredFields, exampleBody) "
            "for automatic self-correction. The client discards it and aborts, forcing a human "
            "round-trip instead of a schema-guided retry."
        ),
        "recommendation": (
            "On invalid_request, rebuild the body from error.fix.exampleBody and retry with a new "
            "Idempotency-Key."
        ),
    },
]
