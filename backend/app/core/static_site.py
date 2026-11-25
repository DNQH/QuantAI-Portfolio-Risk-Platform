"""Serve the built React frontend from the FastAPI app (single-origin deployment).

When ``QUANTAI_FRONTEND_DIST`` points at a Vite ``dist/`` directory (the Docker image
sets this), the API and the UI share one URL:

* ``/api/...``          -> FastAPI routes (registered before this module is mounted)
* ``/assets/...``       -> hashed, immutable JS/CSS bundles (long cache)
* any other GET path   -> ``index.html`` (SPA fallback; the UI uses hash routing)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

logger = logging.getLogger("quantai")

_IMMUTABLE = "public, max-age=31536000, immutable"
_NO_CACHE = "no-cache"


class _CachedStaticFiles(StaticFiles):
    """Static files whose names contain a content hash, so they can be cached forever."""

    async def get_response(self, path, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = _IMMUTABLE
        return response


def mount_frontend(app: FastAPI, dist_dir: Optional[str]) -> bool:
    """Mount the SPA if ``dist_dir`` contains an ``index.html``. Returns True when mounted."""
    if not dist_dir:
        return False
    root = Path(dist_dir).resolve()
    index = root / "index.html"
    if not index.is_file():
        logger.warning("QUANTAI_FRONTEND_DIST=%s has no index.html; UI will not be served.", dist_dir)
        return False

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", _CachedStaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        # Unknown API paths must stay JSON 404s instead of silently returning the UI.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (root / full_path).resolve()
            # Only top-level public files (favicon, robots.txt, ...) and never outside dist/.
            if candidate.is_file() and candidate.parent == root:
                return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": _NO_CACHE})

    logger.info("Serving frontend from %s", root)
    return True
