# MP-043 creator agreement authorization boundary

Date: 2026-08-24

## Decision

Creator revenue-share configuration is private server-side state. PrediBeacon must deny creator-share calculation by default: no creator agreement is usable until an explicit agreement identifier, bounded share value and approval state have been persisted. Revocation immediately makes the agreement unusable. Partner commission economics are not stored in this agreement record and no creator agreement values are exposed through public routes.

The initial implementation is deliberately storage-only. Administrative mutation and creator-facing authentication remain separate work so that this change cannot accidentally create an unauthenticated commercial control surface.

## Current primary-source basis

OWASP Authorization Cheat Sheet recommends least privilege, deny by default, server-side authorization, safe failure handling, and unit/integration tests for authorization logic. PrediBeacon applies those principles here by making the absence of an approved agreement equivalent to no authorization to calculate or expose a creator share.

Source reviewed: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html

## Non-goals

- no public endpoint for agreement terms
- no default or inferred revenue share
- no partner commission configuration
- no creator authentication claim
- no payout execution
