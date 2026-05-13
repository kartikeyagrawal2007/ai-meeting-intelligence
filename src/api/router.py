"""
api/router.py
─────────────
FastAPI routes for the Meeting Intelligence API.

Endpoints:
  POST /api/analyze         — upload audio, start analysis job
  GET  /api/status/{id}     — poll job status + progress
  GET  /api/results/{id}    — fetch completed analysis results
  GET  /api/jobs            — list all jobs
  GET  /api/tokens          — daily token usage
  GET  /api/cache/stats     — cache statistics
  DELETE /api/cache         — clear all cache
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile  # type: ignore[import-untyped]
from fastapi.responses import JSONResponse, PlainTextResponse  # type: ignore[import-untyped]

# Ensure src/ is on the path when this module is imported
SRC_DIR = Path(__file__).parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api import jobs as job_store
from api.jobs import JobStatus
from utils.token_tracker import get_usage, get_all_history
from utils.cache import stats as cache_stats, clear_all as cache_clear
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api")

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac"}
UPLOAD_DIR = Path(__file__).parent.parent.parent / "outputs" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Background worker ─────────────────────────────────────────────────────────

def _run_analysis(job_id: str) -> None:
    """Runs the full analysis pipeline in a background thread."""
    job = job_store.get_job(job_id)
    if not job:
        return

    try:
        # Lazy imports to avoid loading heavy modules at startup
        from utils.chunker import chunk_utterances
        from intelligence.sentiment import analyze_sentiment
        from analytics.participation import analyze_participation
        from analytics.interruptions import analyze_interruptions
        from analytics.quality_score import compute_quality_score
        from audio.preprocess import preprocess_audio
        from transcription.transcriber import transcribe_audio
        from transcription.formatter import format_transcript
        from intelligence.extractor import extract_intelligence
        from intelligence.correction import correct_transcript
        from intelligence.topic_segmenter import segment_topics, segments_to_dict
        from output.recap import render_recap
        from utils.cache import hash_file, get as cache_get, set as cache_set

        # ── Preprocessing ──────────────────────────────────────────────────
        job_store.update_status(job_id, JobStatus.PREPROCESSING, "Preprocessing Audio")
        clean_path = (
            job.audio_path
            if job.skip_preprocess
            else preprocess_audio(job.audio_path)
        )

        # ── Transcription (with caching) ───────────────────────────────────
        job_store.update_status(job_id, JobStatus.TRANSCRIBING, "Transcribing & Diarizing")
        file_hash = hash_file(clean_path)
        cache_key = f"{file_hash}_{job.provider}"
        transcript = cache_get(cache_key, namespace="transcription")

        if transcript is None:
            transcript = transcribe_audio(clean_path, provider=job.provider)
            cache_set(cache_key, transcript, namespace="transcription")
        else:
            log.info(f"Transcription cache hit for job {job_id}")

        transcript = chunk_utterances(transcript, max_words=30)

        # ── Correction ─────────────────────────────────────────────────────
        job_store.update_status(job_id, JobStatus.CORRECTING, "Correcting Transcript")
        if not job.skip_correction:
            transcript = correct_transcript(transcript)

        # ── Analytics (no API calls) ───────────────────────────────────────
        job_store.update_status(job_id, JobStatus.ANALYZING, "Analyzing Participation & Topics")
        participation = analyze_participation(transcript)
        interruptions = analyze_interruptions(transcript)
        topics = segments_to_dict(segment_topics(transcript))
        formatted_transcript = format_transcript(transcript)

        # ── Sentiment ──────────────────────────────────────────────────────
        if not job.skip_sentiment:
            sentiment = analyze_sentiment(transcript)
        else:
            sentiment = {}

        # ── Intelligence extraction (with caching) ─────────────────────────
        job_store.update_status(job_id, JobStatus.EXTRACTING, "Extracting Intelligence")
        intelligence = {}
        if not job.skip_extraction:
            from utils.cache import hash_dict
            transcript_hash = hash_dict({"utterances": [
                u.get("text", "") for u in transcript.get("utterances", [])
            ]})
            intelligence = cache_get(transcript_hash, namespace="extraction")
            if intelligence is None:
                intelligence = extract_intelligence(transcript)
                cache_set(transcript_hash, intelligence, namespace="extraction")
            else:
                log.info(f"Extraction cache hit for job {job_id}")

        # ── Quality score ──────────────────────────────────────────────────
        quality = compute_quality_score(participation, interruptions, sentiment, intelligence)

        # ── Recap ──────────────────────────────────────────────────────────
        recap_md = render_recap(intelligence, job.meeting_title)

        # ── Save results ───────────────────────────────────────────────────
        results = {
            "meeting_title":  job.meeting_title,
            "transcript":     formatted_transcript,
            "utterances":     transcript.get("utterances", []),
            "participation":  participation,
            "interruptions":  interruptions,
            "sentiment":      sentiment,
            "intelligence":   intelligence,
            "topics":         topics,
            "quality_score": {
                "total":       quality.total,
                "rating":      quality.rating,
                "sub_scores": {
                    "participation":          quality.participation_score,
                    "sentiment":              quality.sentiment_score,
                    "decision_and_actions":   quality.decision_score,
                    "interruption_control":   quality.interruption_score,
                    "engagement_consistency": quality.engagement_score,
                },
                "breakdown":   quality.breakdown,
                "diagnostics": quality.diagnostics,
            },
            "recap_markdown": recap_md,
            "token_usage":    get_usage(),
        }

        job_store.set_results(job_id, results)
        job_store.update_status(job_id, JobStatus.COMPLETE, "Complete")
        log.info(f"Job {job_id} complete ✓")

    except Exception as exc:
        log.exception(f"Job {job_id} failed: {exc}")
        job_store.set_error(job_id, str(exc))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze(
    audio: UploadFile = File(...),
    meeting_title: str = Form("Meeting"),
    provider: str = Form("assemblyai"),
    skip_preprocess: bool = Form(False),
    skip_correction: bool = Form(False),
    skip_sentiment: bool = Form(False),
    skip_extraction: bool = Form(False),
):
    """Accept an audio file upload and start an async analysis job."""
    ext = Path(audio.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Save upload to disk
    dest = UPLOAD_DIR / f"{meeting_title.replace(' ', '_')}_{audio.filename}"
    content = await audio.read()
    dest.write_bytes(content)
    log.info(f"Uploaded {audio.filename} ({len(content):,} bytes) → {dest}")

    # Create job
    job = job_store.create_job(
        meeting_title=meeting_title,
        audio_filename=audio.filename,
        audio_path=str(dest),
        provider=provider,
        skip_preprocess=skip_preprocess,
        skip_correction=skip_correction,
        skip_sentiment=skip_sentiment,
        skip_extraction=skip_extraction,
    )

    # Start background thread
    thread = threading.Thread(target=_run_analysis, args=(job.job_id,), daemon=True)
    thread.start()

    return JSONResponse(
        status_code=202,
        content={"job_id": job.job_id, "status": "queued"}
    )


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Poll job status and progress."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job_store.job_to_dict(job)


@router.get("/results/{job_id}")
async def get_results(job_id: str):
    """Fetch full analysis results for a completed job."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if job.status == JobStatus.FAILED:
        raise HTTPException(status_code=500, detail=job.error or "Analysis failed")
    if job.status != JobStatus.COMPLETE:
        raise HTTPException(status_code=202, detail="Analysis still in progress")
    return job.results


@router.get("/results/{job_id}/recap")
async def get_recap(job_id: str):
    """Download the markdown recap for a completed job."""
    job = job_store.get_job(job_id)
    if not job or job.status != JobStatus.COMPLETE:
        raise HTTPException(status_code=404, detail="Results not available")
    recap = job.results.get("recap_markdown", "")
    return PlainTextResponse(
        content=recap,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{job.meeting_title}_recap.md"'},
    )


@router.get("/jobs")
async def list_all_jobs():
    """List all jobs with their status (newest first)."""
    return [job_store.job_to_dict(j) for j in job_store.list_jobs()]


@router.get("/tokens")
async def token_usage():
    """Return today's token usage and history."""
    return {
        "today": get_usage(),
        "history": get_all_history()[:7],  # last 7 days
    }


@router.get("/cache/stats")
async def get_cache_stats():
    return cache_stats()


@router.delete("/cache")
async def clear_cache():
    count = cache_clear()
    return {"cleared": count}
