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

## Stage 2 — clean redeployment

- Observed at: 2026-08-22T15:19:54Z
- Application version: 0.11.0
- Storage writable: true
- Persistent volume configured: true
- Storage identity: `fcb833b0327b062c3335f8b95e1dd636` (unchanged)
- Startup count: 2 (incremented from 1)
- First startup timestamp: unchanged
- Automated publishing enabled: false
- Queue counts: all zero

## Result

**Passed.** The unchanged identity and incremented startup count prove that the same writable SQLite database survived a clean Railway deployment on the mounted Volume.

No content candidate was created and no publication capability was enabled by this test.
