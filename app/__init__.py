from __future__ import annotations

import os
from pathlib import Path


# Railway only guarantees RAILWAY_GIT_COMMIT_SHA for deployments created by a
# GitHub source trigger. Our release workflow can deploy the exact checked-out
# commit with `railway up`, so it writes this tiny non-secret marker into the
# upload bundle. Preserve Railway's native value whenever it is available.
if not os.getenv("RAILWAY_GIT_COMMIT_SHA"):
    marker = Path(__file__).with_name(".deployment_sha")
    if marker.is_file():
        sha = marker.read_text(encoding="utf-8").strip()
        if sha:
            os.environ["RAILWAY_GIT_COMMIT_SHA"] = sha
