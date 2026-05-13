"""
app.py
──────
FastAPI application entry point.
Run with:  uvicorn app:app --reload --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import router

app = FastAPI(
    title="AI Meeting Intelligence API",
    description="Production-grade meeting analysis with transcription, sentiment, and intelligence extraction.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (allow Next.js dev server + production) ───────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "meeting-intelligence-api"}
