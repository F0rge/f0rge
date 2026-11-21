# Shared Rust API errors

Small response plumbing for future Actix apps (P-015/P-022). This crate contains
no app business rules, permissions, identity adapter, database or collector.
No app consumes it yet besides `f0rge-identity`; existing Python/frontend apps
are unchanged.

## Response contract

An explicitly returned `ApiError` produces JSON with exactly one `error` object:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Some fields are invalid.",
    "error_id": "d73fe9f1-9e71-4ad4-bc72-0ab123f6ba00",
    "field_errors": [
      {
        "field": "costs.purchase_price",
        "code": "required",
        "message": "This field is required."
      }
    ]
  }
}
```

| Constructor | HTTP status | Stable code |
| --- | --- | --- |
| `ApiError::validation(fields)` | 422 | `validation_failed` |
| `ApiError::unauthenticated()` | 401 | `unauthenticated` |
| `ApiError::forbidden()` | 403 | `forbidden` |
| `ApiError::not_found()` | 404 | `not_found` |
| `ApiError::conflict()` | 409 | `conflict` |
| `ApiError::internal()` / `internal_from(cause)` | 500 | `internal_error` |

Public messages are fixed. `field_errors` is always an array and is empty for
non-validation errors. Field codes are `required`, `invalid` and `out_of_range`,
with fixed messages. Their static schema paths are ASCII identifiers separated
by dots, at most 128 bytes: each segment starts with a letter or underscore,
then contains letters, digits or underscores. Array indices and bracket paths
are unsupported. Apps supply schema metadata, never submitted keys or values.

Each error generates its own UUIDv4 once. Re-rendering it preserves the same
identifier. Request headers cannot supply or replace it. This is an error
correlation identifier, not an installed request-tracing system.

Responses set `Content-Type: application/json` and `Cache-Control: no-store`.
`internal_from` discards the cause; the response, `Display`, `Debug` and
`Error::source` expose no retained internal diagnostics. Apps must arrange
separately reviewed, redacted telemetry with the error identifier where needed.

## Run through Nx

```sh
npx nx run-many -t=format-check,lint,test,build --projects=f0rge-api-errors --parallel=1
node .github/rust/guard.mjs
```

The standalone package owns its committed `Cargo.lock`; no root Cargo workspace
is introduced. All targets use the existing [Rust/Nx contract](../../../.github/rust/README.md)
and pinned toolchain. Initial Nx caching remains disabled. Cargo intermediates
stay in ignored `target/nx/f0rge-api-errors/`.

After the build, start the synthetic loopback-only probe:

```sh
./target/nx/f0rge-api-errors/debug/examples/local_errors
curl -i http://127.0.0.1:8872/
curl -i http://127.0.0.1:8872/errors/validation
curl -i http://127.0.0.1:8872/errors/forbidden
curl -i http://127.0.0.1:8872/errors/conflict
curl -i http://127.0.0.1:8872/errors/internal
```

The probe binds only `127.0.0.1:8872`, uses synthetic constants and makes no
database, file-data, credential or external-service calls. Stop it with Ctrl-C.

## Integration limits

The [Actix `ResponseError` adapter](https://actix.rs/docs/errors/) maps only
explicitly returned `ApiError` values. It does not normalize JSON/path extractor
failures, default 404/405 responses or arbitrary framework errors. A consuming
app needs tested boundary wiring before claiming one complete error contract.
No authentication scheme/challenge, permission enforcement, API generator,
typed React client or shared frontend error handler is selected or installed.
The 409 mapping represents an edit conflict; app services still detect it.

P-021 and the full P-022 remain incomplete. These tests do not certify an app,
database, ARM64 image, release pipeline or deployed runtime. No production
deployment is part of this library.

Dependencies are locked to the tested graph. The selected Actix Web 4.19.0 and
Actix HTTP 3.21.0 are above the fixes listed in
[RUSTSEC-2026-0447](https://rustsec.org/advisories/RUSTSEC-2026-0447.html).
Compression features are disabled. This version check is not a complete
transitive dependency audit.
