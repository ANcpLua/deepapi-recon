> _Sample of the `contract-audit` job summary — CI regenerates this live on every push
> ([latest run](https://github.com/ANcpLua/deepapi-recon/actions/workflows/contract-audit.yml))._

## DeepAPI client contract audit

Audited `tests/_naive_client.py` against the SKILL.md error contract — **3 findings**. These are client-side compliance gaps, not defects in DeepAPI.

| gap | naive | fixed |
|---|:---:|:---:|
| 1. same-key idempotency on retry | ❌ | ✅ |
| 2. bounded retries (no infinite loop) | ❌ | ✅ |
| 3. error.fix self-correction | ❌ | ✅ |

### Findings
| sev | rule | location | issue |
|---|---|---|---|
| 🔴 error | `deepapi-client/idempotency-key-not-reused` | `tests/_naive_client.py:45` | Retry mints a new Idempotency-Key, breaking same-key idempotency |
| 🔴 error | `deepapi-client/unbounded-retry-recursion` | `tests/_naive_client.py:59` | Unbounded retry recursion on persistent retryable errors |
| 🟠 warning | `deepapi-client/error-fix-ignored` | `tests/_naive_client.py:62` | invalid_request self-correction (error.fix) is ignored |
