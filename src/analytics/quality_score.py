"""
analytics/quality_score.py
──────────────────────────
Computes a 0-100 composite Meeting Quality Score from already-computed
analytics data.  Zero extra API calls — everything is derived from the
data already collected by participation, interruption, sentiment, and
intelligence modules.

Score breakdown (100 pts total):
  ┌───────────────────────────────┬──────┐
  │ Component                     │ Max  │
  ├───────────────────────────────┼──────┤
  │ Participation Balance         │  25  │
  │ Sentiment Health              │  25  │
  │ Decision & Action Density     │  25  │
  │ Interruption Control          │  15  │
  │ Engagement Consistency        │  10  │
  └───────────────────────────────┴──────┘
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data class for a transparent, explainable score
# ---------------------------------------------------------------------------

@dataclass
class QualityScore:
    """Full decomposed meeting quality score."""

    # Sub-scores (0–100 for each component before weighting)
    participation_score: float = 0.0   # 25 pts
    sentiment_score: float = 0.0       # 25 pts
    decision_score: float = 0.0        # 25 pts
    interruption_score: float = 0.0    # 15 pts
    engagement_score: float = 0.0      # 10 pts

    # Weighted composite
    total: float = 0.0

    # Human-readable rating band
    rating: str = "Unknown"

    # Detailed breakdown for display / JSON export
    breakdown: dict = field(default_factory=dict)

    # Raw diagnostic metrics (useful for debugging / reporting)
    diagnostics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Weights (must sum to 1.0)
# ---------------------------------------------------------------------------

WEIGHTS = {
    "participation": 0.25,
    "sentiment":     0.25,
    "decision":      0.25,
    "interruption":  0.15,
    "engagement":    0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _gini_coefficient(shares: list[float]) -> float:
    """
    Gini coefficient of speaking-time shares (0 = perfect equality, 1 = monopoly).
    We use the closed-form formula for discrete populations.
    """
    n = len(shares)
    if n <= 1:
        return 0.0
    sorted_s = sorted(shares)
    numerator = sum((i + 1) * x for i, x in enumerate(sorted_s))
    total = sum(sorted_s)
    if total == 0:
        return 0.0
    return (2 * numerator) / (n * total) - (n + 1) / n


def _std_dev(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------

def _score_participation(participation: dict) -> tuple[float, dict, dict]:
    """
    25-pt component: rewards balanced talking time across speakers.

    Approach:
    - Compute Gini coefficient of speaking shares.
    - Perfect equality (Gini=0) → 100; monopoly (Gini=1) → 0.
    - Bonus: penalise if any speaker has <5% share (silent participant).
    """
    if not participation:
        return 0.0, {"reason": "no participation data"}, {}

    shares = [v["speaking_share_percent"] / 100.0 for v in participation.values()]
    n_speakers = len(shares)

    if n_speakers == 1:
        # Solo speaker — no balance possible, give 50 (neutral)
        raw = 50.0
        gini = 0.0
    else:
        gini = _gini_coefficient(shares)
        # Gini 0 → raw 100, Gini 1 → raw 0
        raw = _clamp((1 - gini) * 100)

    # Penalty: how many speakers are effectively silent (<5% share)?
    silent_speakers = sum(1 for s in shares if s < 0.05)
    silence_penalty = silent_speakers * 10.0
    raw = _clamp(raw - silence_penalty)

    diagnostics = {
        "n_speakers": n_speakers,
        "gini_coefficient": round(gini, 4),
        "silent_speakers": silent_speakers,
        "speaking_shares": {
            spk: round(v["speaking_share_percent"], 1)
            for spk, v in participation.items()
        },
    }
    breakdown = {
        "raw_balance": round((1 - gini) * 100, 1),
        "silence_penalty": round(silence_penalty, 1),
        "final": round(raw, 1),
    }
    return raw, breakdown, diagnostics


def _score_sentiment(sentiment: dict) -> tuple[float, dict, dict]:
    """
    25-pt component: rewards positive/neutral sentiment with low variance.

    Formula:
    - Base score: linear map of mean sentiment score (-1…1 → 0…100).
    - Variance penalty: high std-dev in scores → meeting may be volatile.
    - Frustration penalty: each frustrated utterance across ALL speakers.
    """
    if not sentiment:
        return 50.0, {"reason": "sentiment not run, defaulting to 50"}, {}

    timeline = sentiment.get("timeline", [])
    if not timeline:
        return 50.0, {"reason": "empty timeline"}, {}

    scores = [utt.get("score", 0.0) for utt in timeline]
    mean_score = sum(scores) / len(scores)
    std = _std_dev(scores)

    # Map mean sentiment -1…1 → 0…100
    base = _clamp((mean_score + 1) / 2 * 100)

    # Variance penalty (std can be max 1.0 in theory): up to -20 pts
    variance_penalty = _clamp(std * 20, 0, 20)

    # Frustration penalty: -3 pts per frustrated utterance (capped at -20)
    frustrated_count = sum(
        1 for utt in timeline
        if utt.get("flags", {}).get("is_frustrated", False)
    )
    frustration_penalty = _clamp(frustrated_count * 3, 0, 20)

    raw = _clamp(base - variance_penalty - frustration_penalty)

    # Sentiment variance across the meeting timeline (positive/negative swings)
    sentiment_labels = [utt.get("sentiment", "neutral") for utt in timeline]
    negative_pct = round(
        sentiment_labels.count("negative") / len(sentiment_labels) * 100, 1
    ) if sentiment_labels else 0.0

    diagnostics = {
        "mean_sentiment_score": round(mean_score, 4),
        "std_dev": round(std, 4),
        "frustrated_utterances": frustrated_count,
        "negative_pct": negative_pct,
        "sample_size": len(scores),
    }
    breakdown = {
        "base_from_mean": round(base, 1),
        "variance_penalty": round(variance_penalty, 1),
        "frustration_penalty": round(frustration_penalty, 1),
        "final": round(raw, 1),
    }
    return raw, breakdown, diagnostics


def _score_decisions(
    intelligence: dict,
    participation: dict,
) -> tuple[float, dict, dict]:
    """
    25-pt component: rewards concrete outcomes relative to meeting length.

    Rate is measured as (action_items + decisions) per 10 minutes of meeting.
    Target rate: 2+ items per 10 min → 100 pts.
    """
    if not intelligence:
        return 25.0, {"reason": "intelligence data missing, defaulting to 25"}, {}

    n_actions = len(intelligence.get("action_items", []))
    n_decisions = len(intelligence.get("decisions", []))
    n_uncertain = len(intelligence.get("uncertain_action_items", [])) + \
                  len(intelligence.get("uncertain_decisions", []))
    n_follow_ups = len(intelligence.get("follow_ups", []))

    total_items = n_actions + n_decisions

    # Estimate meeting duration in minutes from participation data
    total_speaking_secs = sum(
        v["speaking_time_seconds"] for v in participation.values()
    ) if participation else 0
    # Speaking time ≈ 80% of actual meeting time (silence gap heuristic)
    meeting_minutes = (total_speaking_secs / 0.80) / 60 if total_speaking_secs > 0 else 10

    # Items per 10 minutes; target is ≥2 per 10 min
    if meeting_minutes > 0:
        rate_per_10min = (total_items / meeting_minutes) * 10
    else:
        rate_per_10min = 0.0

    # Map rate to score: 0 → 0, 2 → 100, >2 → capped at 100
    base = _clamp(rate_per_10min / 2 * 100)

    # Bonus for high confidence outcomes
    high_conf_actions = sum(
        1 for a in intelligence.get("action_items", [])
        if a.get("confidence", 0) >= 0.85
    )
    bonus = _clamp(high_conf_actions * 5, 0, 15)

    # Penalty if many uncertain items relative to confirmed
    uncertainty_ratio = n_uncertain / max(total_items + n_uncertain, 1)
    uncertainty_penalty = _clamp(uncertainty_ratio * 15, 0, 15)

    raw = _clamp(base + bonus - uncertainty_penalty)

    diagnostics = {
        "action_items": n_actions,
        "decisions": n_decisions,
        "uncertain_items": n_uncertain,
        "follow_ups": n_follow_ups,
        "meeting_minutes_estimated": round(meeting_minutes, 1),
        "rate_per_10min": round(rate_per_10min, 2),
    }
    breakdown = {
        "base_from_rate": round(base, 1),
        "high_confidence_bonus": round(bonus, 1),
        "uncertainty_penalty": round(uncertainty_penalty, 1),
        "final": round(raw, 1),
    }
    return raw, breakdown, diagnostics


def _score_interruptions(
    interruptions: list,
    participation: dict,
) -> tuple[float, dict, dict]:
    """
    15-pt component: fewer interruptions → higher score.

    Normalised by total utterances so a longer meeting isn't automatically penalised.
    """
    total_utterances = sum(
        v.get("utterance_count", 0) for v in participation.values()
    ) if participation else 1

    n_interruptions = len(interruptions) if interruptions else 0

    if total_utterances == 0:
        return 75.0, {"reason": "no utterances to normalise"}, {}

    interruption_rate = n_interruptions / total_utterances  # 0…1+

    # 0 interruptions → 100; rate ≥ 0.3 (30%) → 0
    raw = _clamp((1 - interruption_rate / 0.30) * 100)

    # Identify repeat interrupters (>2 interruptions from same speaker)
    from collections import Counter
    interrupter_counts = Counter(
        item.get("interrupter") for item in (interruptions or [])
    )
    repeat_interrupters = {
        spk: cnt for spk, cnt in interrupter_counts.items() if cnt > 2
    }

    # Extra penalty for serial interrupters
    repeat_penalty = len(repeat_interrupters) * 5.0
    raw = _clamp(raw - repeat_penalty)

    diagnostics = {
        "total_interruptions": n_interruptions,
        "total_utterances": total_utterances,
        "interruption_rate": round(interruption_rate, 4),
        "repeat_interrupters": repeat_interrupters,
    }
    breakdown = {
        "base_from_rate": round(_clamp((1 - interruption_rate / 0.30) * 100), 1),
        "repeat_interrupter_penalty": round(repeat_penalty, 1),
        "final": round(raw, 1),
    }
    return raw, breakdown, diagnostics


def _score_engagement(sentiment: dict, participation: dict) -> tuple[float, dict, dict]:
    """
    10-pt component: rewards consistent per-speaker sentiment across the timeline
    (i.e., no single speaker is systematically negative / disengaged).

    Also rewards speakers who vary their energy (not monotone).
    """
    if not sentiment or not participation:
        return 50.0, {"reason": "insufficient data"}, {}

    speaker_summary = sentiment.get("speaker_summary", {})
    if not speaker_summary:
        return 50.0, {"reason": "no speaker summary"}, {}

    avg_scores = [v["average_score"] for v in speaker_summary.values()]
    if not avg_scores:
        return 50.0, {}, {}

    # How consistent is sentiment across speakers?
    inter_speaker_std = _std_dev(avg_scores)
    consistency = _clamp((1 - inter_speaker_std) * 100)

    # Penalise systematically disengaged speakers (avg score < -0.3)
    disengaged = sum(1 for s in avg_scores if s < -0.3)
    disengaged_penalty = disengaged * 15.0

    # Energy diversity bonus: having both high and low energy moments is natural
    timeline = sentiment.get("timeline", [])
    energies = [utt.get("energy", "medium") for utt in timeline]
    energy_types = set(energies)
    energy_diversity_bonus = 10.0 if len(energy_types) >= 2 else 0.0

    raw = _clamp(consistency - disengaged_penalty + energy_diversity_bonus)

    diagnostics = {
        "inter_speaker_std": round(inter_speaker_std, 4),
        "disengaged_speakers": disengaged,
        "energy_types_seen": list(energy_types),
    }
    breakdown = {
        "consistency_score": round(consistency, 1),
        "disengaged_penalty": round(disengaged_penalty, 1),
        "energy_diversity_bonus": round(energy_diversity_bonus, 1),
        "final": round(raw, 1),
    }
    return raw, breakdown, diagnostics


# ---------------------------------------------------------------------------
# Rating bands
# ---------------------------------------------------------------------------

def _rating_band(total: float) -> str:
    if total >= 85:
        return "Excellent"
    elif total >= 70:
        return "Good"
    elif total >= 55:
        return "Fair"
    elif total >= 40:
        return "Needs Improvement"
    else:
        return "Poor"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_quality_score(
    participation: dict,
    interruptions: list,
    sentiment: dict,
    intelligence: dict,
) -> QualityScore:
    """
    Compute the composite 0-100 Meeting Quality Score.

    Args:
        participation:  Output of analytics.participation.analyze_participation()
        interruptions:  Output of analytics.interruptions.analyze_interruptions()
        sentiment:      Output of intelligence.sentiment.analyze_sentiment()
        intelligence:   Output of intelligence.extractor.extract_intelligence()

    Returns:
        QualityScore dataclass with full breakdown.
    """
    log.info("Computing meeting quality score...")

    # --- Component scores (0-100 each) ---
    p_score, p_bd, p_diag = _score_participation(participation)
    s_score, s_bd, s_diag = _score_sentiment(sentiment)
    d_score, d_bd, d_diag = _score_decisions(intelligence, participation)
    i_score, i_bd, i_diag = _score_interruptions(interruptions, participation)
    e_score, e_bd, e_diag = _score_engagement(sentiment, participation)

    # --- Weighted composite ---
    weighted = (
        p_score * WEIGHTS["participation"]
        + s_score * WEIGHTS["sentiment"]
        + d_score * WEIGHTS["decision"]
        + i_score * WEIGHTS["interruption"]
        + e_score * WEIGHTS["engagement"]
    )
    total = round(_clamp(weighted), 1)
    rating = _rating_band(total)

    qs = QualityScore(
        participation_score=round(p_score, 1),
        sentiment_score=round(s_score, 1),
        decision_score=round(d_score, 1),
        interruption_score=round(i_score, 1),
        engagement_score=round(e_score, 1),
        total=total,
        rating=rating,
        breakdown={
            "participation": p_bd,
            "sentiment":     s_bd,
            "decision":      d_bd,
            "interruption":  i_bd,
            "engagement":    e_bd,
            "weights":       WEIGHTS,
        },
        diagnostics={
            "participation": p_diag,
            "sentiment":     s_diag,
            "decision":      d_diag,
            "interruption":  i_diag,
            "engagement":    e_diag,
        },
    )

    log.info(
        f"Quality score: {total}/100 ({rating}) | "
        f"P={qs.participation_score} S={qs.sentiment_score} "
        f"D={qs.decision_score} I={qs.interruption_score} E={qs.engagement_score}"
    )

    return qs


def format_quality_report(qs: QualityScore) -> str:
    """
    Returns a pretty-printed, human-readable quality report string
    suitable for printing to console or appending to a recap.
    """
    bar_len = 30
    filled = int(qs.total / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    lines = [
        "",
        "╔══════════════════════════════════════════════╗",
        f"║  MEETING QUALITY SCORE: {qs.total:>5}/100  [{qs.rating}]  ║",
        f"║  [{bar}]  ║",
        "╠══════════════════════════════════════════════╣",
        f"║  Participation Balance  : {qs.participation_score:>5}/100  (wt 25%) ║",
        f"║  Sentiment Health       : {qs.sentiment_score:>5}/100  (wt 25%) ║",
        f"║  Decision & Action Rate : {qs.decision_score:>5}/100  (wt 25%) ║",
        f"║  Interruption Control   : {qs.interruption_score:>5}/100  (wt 15%) ║",
        f"║  Engagement Consistency : {qs.engagement_score:>5}/100  (wt 10%) ║",
        "╚══════════════════════════════════════════════╝",
    ]

    # Diagnostics summary
    diag_p = qs.diagnostics.get("participation", {})
    diag_s = qs.diagnostics.get("sentiment", {})
    diag_d = qs.diagnostics.get("decision", {})
    diag_i = qs.diagnostics.get("interruption", {})

    lines.append("")
    lines.append("Key Diagnostics:")
    if diag_p:
        lines.append(
            f"  • {diag_p.get('n_speakers', '?')} speakers | "
            f"Gini={diag_p.get('gini_coefficient', '?')} | "
            f"Silent speakers={diag_p.get('silent_speakers', 0)}"
        )
    if diag_s:
        lines.append(
            f"  • Mean sentiment={diag_s.get('mean_sentiment_score', '?')} | "
            f"Negative={diag_s.get('negative_pct', '?')}% | "
            f"Frustrated={diag_s.get('frustrated_utterances', 0)}"
        )
    if diag_d:
        lines.append(
            f"  • {diag_d.get('action_items', 0)} action items | "
            f"{diag_d.get('decisions', 0)} decisions | "
            f"Rate={diag_d.get('rate_per_10min', 0)}/10min"
        )
    if diag_i:
        lines.append(
            f"  • {diag_i.get('total_interruptions', 0)} interruptions "
            f"({diag_i.get('interruption_rate', 0):.1%} of turns)"
        )

    return "\n".join(lines)
