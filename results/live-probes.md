# Live probes (unauthenticated, $0)

Captured against production `deepapi.co`. No `DEEPAPI_API_KEY` was sent, so no
billed work runs — a `401` is the expected, correct result.

## `GET /v1/health` → 200

```
$ curl -s -w 'HTTP %{http_code}\n' https://deepapi.co/v1/health
HTTP 200
{"ok":true,"skillVersion":"d60536539c35"}
```

## `POST /v1/search/web` (no key) → 401

```
$ curl -s -w 'HTTP %{http_code}\n' -X POST https://deepapi.co/v1/search/web \
       -H 'Content-Type: application/json' -d '{"query":"test"}'
HTTP 401
{"requestId":null,"route":"/v1/search/web","capability":"search.web","status":"failed",
 "replayed":false,"costFinal":false,"debitMicrousd":null,"output":null,"balance":null,
 "next":null,"error":{"code":"missing_api_key","message":"Missing bearer API key",
 "field":null,"requiredScope":null,"retryable":false,"retryAfterSecs":null,
 "docsUrl":"https://deepapi.co/llms.txt",
 "hint":"Send `Authorization: Bearer $DEEPAPI_API_KEY`."},"skillVersion":"d60536539c35"}
```

The auth failure returns the **same envelope shape as a success** (`requestId`,
`route`, `capability`, `status`, `debitMicrousd`, `next`, `error`, `skillVersion`)
— machine-readable, so an agent can branch on `error.code` and self-correct.
