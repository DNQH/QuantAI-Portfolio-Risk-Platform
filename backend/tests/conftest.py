"""Shared pytest configuration.

Points the default SQLite database at a throw-away temp file BEFORE ``app.main`` is
imported (it builds a module-level app), so running the suite never writes to the
developer's real ``backend/quantai.db``.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["QUANTAI_DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="quantai-tests-"), "quantai-test.db")

# Hermetic tests: ignore any developer .env and drop provider credentials inherited from the
# shell, so a local GEMINI/FINNHUB/TWELVEDATA key can neither change results nor be spent.
os.environ["QUANTAI_DISABLE_DOTENV"] = "1"
for _key in (
    "GEMINI_API_KEY",
    "FINNHUB_API_KEY",
    "TWELVEDATA_API_KEY",
    "EODHD_API_KEY",
    "MASSIVE_API_KEY",
    "SSI_API_KEY",
    "SSI_API_SECRET",
    "SSI_CONSUMER_ID",
    "SSI_CONSUMER_SECRET",
    "VNSTOCK_API_KEY",
):
    os.environ.pop(_key, None)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
