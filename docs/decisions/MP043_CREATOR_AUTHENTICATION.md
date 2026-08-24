# MP-043 creator authentication boundary

Date: 2026-08-24

## Decision

PrediBeacon creator self-service APIs use an admin-provisioned opaque bearer credential as the initial authentication boundary. The raw credential is generated with Python's `secrets` CSPRNG, returned only once at creation, sent only in the `X-PrediBeacon-Creator-Token` request header, and persisted only as a SHA-256 hash. The database maps the credential to exactly one creator identity; self-service routes derive identity from that mapping and do not accept a caller-selected creator identifier.

Credential creation and revocation are admin-only. Revoked credentials fail closed immediately. Sensitive creator responses set `Cache-Control: no-store`. Public creator pages remain public market-selection pages and do not receive financial/account information.

This is deliberately an API authentication foundation, not a claim that a full consumer account/identity-provider experience is complete. A future interactive creator account system may replace the opaque token with an authorized external identity provider while preserving the same server-side identity and least-privilege boundary.

## Current primary-source basis

- OWASP REST Security Cheat Sheet: credentials and API keys must be protected by HTTPS, must not appear in URLs, should be required on protected endpoints, management endpoints require strong authentication, sensitive API responses should use `Cache-Control: no-store`, and authorization must be enforced server-side.
  - https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- OWASP Cryptographic Storage Cheat Sheet: security-sensitive random tokens must use a cryptographically secure random number generator; Python's `secrets` module is identified as the CSPRNG choice.
  - https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- OWASP Authorization Cheat Sheet: deny by default, least privilege, server-side authorization and authorization regression tests.
  - https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html

## Security properties

- raw creator tokens are never persisted
- tokens are not accepted through URL parameters
- creator identity is derived from the credential, not supplied by the caller
- admin authentication is required to issue or revoke creator credentials
- invalid or revoked tokens return a generic unauthorized response
- private creator revenue responses are not cacheable
- no partner identifier, commission percentage, revenue-share percentage or agreement configuration is added to any public response

## Remaining work

A browser-oriented creator account/login experience and any external identity-provider integration remain separate product work. The protected API identity boundary can operate without those external dependencies.
