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

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
