# Production browser smoke commit-status evidence

Date: 2026-08-24

## Decision

The production browser smoke publishes a dedicated GitHub commit status named `predibeacon/production-browser-smoke` on the exact commit SHA whose deployment is being tested. The status is `success` only when all real-production browser suites pass and `failure` otherwise. It links back to the workflow run for inspection.

For workflow-run executions triggered by CI on `main`, the status is attached to `github.event.workflow_run.head_sha`. Scheduled or manually dispatched executions use the workflow's current `GITHUB_SHA`.

The smoke test step uses `continue-on-error` only so that the final status-publishing step can run even after a test failure. The publishing step exits non-zero when the smoke did not pass, preserving the workflow's failure semantics.

## Primary-source basis

GitHub's REST commit-status documentation describes commit statuses as the mechanism for CI/external services to mark a commit `success`, `failure`, `error` or `pending`, supports a distinct `context`, and recommends a description and `target_url` to make the evidence useful in the GitHub UI. Creating a status requires repository Commit statuses write permission.

Source reviewed: https://docs.github.com/en/rest/commits/statuses

## Why this matters for PrediBeacon

The project requires post-merge production evidence before requirements such as MP-024 and MP-037 can become terminal. A commit status makes that evidence machine-readable by the same release tooling that already reads combined commit status, instead of depending on manual inspection of the Actions page.

The status contains no secrets, partner identifiers, commercial terms or user data.
