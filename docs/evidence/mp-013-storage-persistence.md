# Railway Volume persistence validation

Requirement: MP-013 durable content queue storage.

## Stage 1 — initial deployment

- Observed at: 2026-08-22T15:17:45Z
- Application version: 0.11.0
- Storage writable: true
- Persistent volume configured: true
- Storage identity: `fcb833b0327b062c3335f8b95e1dd636`
- Startup count: 1
- Automated publishing enabled: false
- Queue counts: all zero

## Stage 2 — redeployment

Pending. The merge of this evidence document intentionally triggers a clean Railway deployment. Validation passes only if the public status subsequently reports:

1. the same storage identity;
2. a startup count greater than 1;
3. writable storage and persistent volume configuration still true;
4. automated publishing still false.

No content candidate is created and no publication capability is enabled by this test.
