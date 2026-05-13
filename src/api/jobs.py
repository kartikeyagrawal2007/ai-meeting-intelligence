"""
api/jobs.py
───────────
In-memory job queue for async meeting analysis.

Each job goes through these stages:
  queued → preprocessing → transcribing → correcting →
  analyzing → extracting → complete | failed
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    QUEUED         = "queued"
    PREPROCESSING  = "preprocessing"
    TRANSCRIBING   = "transcribing"
    CORRECTING     = "correcting"
    ANALYZING      = "analyzing"
    EXTRACTING     = "extracting"
    COMPLETE       = "complete"
    FAILED         = "failed"


# Ordered pipeline stages for progress tracking
PIPELINE_STAGES = [
    JobStatus.QUEUED,
    JobStatus.PREPROCESSING,
    JobStatus.TRANSCRIBING,
    JobStatus.CORRECTING,
    JobStatus.ANALYZING,
    JobStatus.EXTRACTING,
    JobStatus.COMPLETE,
]


@dataclass
class Job:
    job_id: str
    meeting_title: str
    audio_filename: str
    audio_path: str
    provider: str = "assemblyai"

    # Pipeline flags
    skip_preprocess: bool = False
    skip_correction: bool = False
    skip_sentiment: bool = False
    skip_extraction: bool = False

    # Status
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0           # 0-100
    current_stage: str = "Queued"
    error: str | None = None

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: str | None = None
    completed_at: str | None = None

    # Results (populated when complete)
    results: dict[str, Any] = field(default_factory=dict)


# ── Global in-memory store ────────────────────────────────────────────────────

_jobs: dict[str, Job] = {}
_lock = threading.Lock()


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_job(
    meeting_title: str,
    audio_filename: str,
    audio_path: str,
    provider: str = "assemblyai",
    skip_preprocess: bool = False,
    skip_correction: bool = False,
    skip_sentiment: bool = False,
    skip_extraction: bool = False,
) -> Job:
    job = Job(
        job_id=str(uuid.uuid4()),
        meeting_title=meeting_title,
        audio_filename=audio_filename,
        audio_path=audio_path,
        provider=provider,
        skip_preprocess=skip_preprocess,
        skip_correction=skip_correction,
        skip_sentiment=skip_sentiment,
        skip_extraction=skip_extraction,
    )
    with _lock:
        _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def list_jobs() -> list[Job]:
    """Return all jobs, newest first."""
    return sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)


def update_status(job_id: str, status: JobStatus, stage_label: str = "") -> None:
    job = _jobs.get(job_id)
    if not job:
        return

    job.status = status

    # Map status → progress %
    stage_progress = {
        JobStatus.QUEUED:        0,
        JobStatus.PREPROCESSING: 10,
        JobStatus.TRANSCRIBING:  30,
        JobStatus.CORRECTING:    50,
        JobStatus.ANALYZING:     65,
        JobStatus.EXTRACTING:    80,
        JobStatus.COMPLETE:      100,
        JobStatus.FAILED:        job.progress,  # freeze at last known progress
    }
    job.progress = stage_progress.get(status, job.progress)
    job.current_stage = stage_label or status.value.title()

    if status == JobStatus.PREPROCESSING and not job.started_at:
        job.started_at = datetime.utcnow().isoformat()

    if status in (JobStatus.COMPLETE, JobStatus.FAILED):
        job.completed_at = datetime.utcnow().isoformat()


def set_error(job_id: str, error: str) -> None:
    job = _jobs.get(job_id)
    if job:
        job.status = JobStatus.FAILED
        job.error = error
        job.completed_at = datetime.utcnow().isoformat()


def set_results(job_id: str, results: dict) -> None:
    job = _jobs.get(job_id)
    if job:
        job.results = results


def job_to_dict(job: Job) -> dict:
    return {
        "job_id":          job.job_id,
        "meeting_title":   job.meeting_title,
        "audio_filename":  job.audio_filename,
        "provider":        job.provider,
        "status":          job.status.value,
        "progress":        job.progress,
        "current_stage":   job.current_stage,
        "error":           job.error,
        "created_at":      job.created_at,
        "started_at":      job.started_at,
        "completed_at":    job.completed_at,
        "has_results":     bool(job.results),
    }
