# PrediBeacon Commercial API Operations

## Authentication

Commercial clients send the one-time credential in `X-PrediBeacon-API-Key`. Credentials begin with `pb_live_`; PrediBeacon stores only a SHA-256 hash. Never place a key in a URL, browser bundle, log or support message.

## Available scopes

- `markets:read`: normalized discovery data.
- `history:read`: bounded probability and volume history.

Every successful authorization atomically consumes one request from the key's UTC daily quota. Missing, invalid, revoked and incorrectly scoped credentials fail closed.

## Administrative lifecycle

Protected administration requires the internal admin token.

- `POST /api/v1/admin/api-keys`: create a one-time credential.
- `GET /api/v1/admin/api-keys`: list metadata only; secrets are never returned.
- `POST /api/v1/admin/api-keys/{key_id}/rotate`: atomically create a replacement and revoke the previous credential.
- `DELETE /api/v1/admin/api-keys/{key_id}`: revoke immediately.

Rotate a key if it may have been exposed. Distribute the replacement through an approved secret manager, verify the client, then remove all copies of the old secret.

## Request tracing and errors

Every response includes `X-Request-ID`. A caller may supply an identifier containing 8–64 letters, digits, dots, underscores or hyphens; invalid identifiers are replaced. `Server-Timing` reports application processing duration. Write requests declaring more than 1 MiB are rejected with HTTP 413.

Common responses:

- 401: missing, invalid, revoked or insufficiently scoped key.
- 404: requested market or administrative key does not exist.
- 413: declared request body exceeds the service limit.
- 429: UTC daily quota exhausted.
