from __future__ import annotations

from app.main import app
from app.routes.commercial_intelligence import router as commercial_intelligence_router


app.include_router(commercial_intelligence_router)
