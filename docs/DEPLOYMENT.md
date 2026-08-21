# MarketPulse deployment

## Railway staging baseline

MarketPulse uses Railway as the initial staging/runtime provider and GitHub as the source of truth.

Deployment policy:

1. Code change enters GitHub.
2. GitHub Actions must pass.
3. Railway should be configured with **Wait for CI** before autodeploying the tracked branch.
4. Railway starts the web service with the command in `railway.toml`.
5. `/health` must return HTTP 200 before Railway promotes a new deployment.
6. Production remains separate from staging and is enabled only after release gates pass.

The application listens on Railway's injected `PORT` variable.

## Required Railway settings

- Source repository: `dbdanielbaracho/MARKETPULSE`
- Initial environment: `staging`
- Tracked branch: `main` until the release workflow is expanded
- Wait for CI: enabled
- Config file: `/railway.toml`
- Healthcheck: `/health`

## Secrets

Secrets must live in Railway/GitHub secret stores, never committed. `.env.example` contains names only.

## Future service split

The first deployment may run the refresh loop inside the web process for speed of launch. Before scale-out or more than one web replica, ingestion/publishing schedules must move into an independently deployed worker/service to prevent duplicate jobs. This boundary is already represented in architecture and must not be bypassed by horizontal scaling.
