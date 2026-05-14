from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from api.router import router  # noqa: E402
