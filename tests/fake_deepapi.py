"""In-process fake DeepAPI — no network, no key, no billing.

Scripts a sequence of responses and captures every request so a test can assert
what the client actually did: which Idempotency-Key it sent, how many attempts
it made, and what body it finally submitted. Used to pin the retry/idempotency
contract for both the naive baseline and the fixed client.
"""
import io, json, os, time, importlib.util
import urllib.request, urllib.error

os.environ.setdefault("DEEPAPI_API_KEY", "test-key")   # clients read this at import
time.sleep = lambda *a, **k: None                       # never actually wait in tests


class _Resp:
    """Minimal stand-in for an http response (context-manager + .read())."""
    def __init__(self, obj):
        self._b = json.dumps(obj).encode()
    def read(self, *a):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


class FakeDeepAPI:
    """A scripted urlopen. `script` is a list of steps:
        ("ok",  body_dict)            -> HTTP 200 with that JSON
        ("err", http_int, envelope)   -> raises HTTPError carrying that envelope
    If the client makes more calls than there are steps, the LAST step repeats —
    which is how we model a *persistent* error (for the unbounded-retry test).
    """
    def __init__(self, script):
        self.script = list(script)
        self.calls = []                                 # one dict per request

    def __call__(self, req, data=None):
        idem = next((v for k, v in req.header_items() if k.lower() == "idempotency-key"), None)
        self.calls.append({
            "method": req.get_method(),
            "url": req.full_url,
            "idem": idem,
            "body": json.loads(data.decode()) if data else None,
        })
        step = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if step[0] == "ok":
            return _Resp(step[1])
        raise urllib.error.HTTPError(req.full_url, step[1], "err", {}, io.BytesIO(json.dumps(step[2]).encode()))

    @property
    def keys(self):
        return [c["idem"] for c in self.calls]

    @property
    def n(self):
        return len(self.calls)


def install(fake):
    """Route both clients' urllib calls through the fake for this scenario."""
    urllib.request.urlopen = fake


def load_client(path, name):
    """Import a client module by file path (lets us load naive + fixed side by side)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
