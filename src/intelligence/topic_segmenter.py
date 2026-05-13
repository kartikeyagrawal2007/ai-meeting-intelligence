"""
intelligence/topic_segmenter.py
────────────────────────────────
Pure-Python topic segmentation using a sliding window approach.

Algorithm:
  1. Represent each utterance as a TF-IDF-style keyword bag.
  2. Slide a window of W utterances, compute cosine similarity
     between adjacent windows.
  3. Low-similarity transitions → topic boundary.
  4. Label each segment by extracting the top keywords.

No API calls. No external ML models. Works with any transcript.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from utils.logger import get_logger

log = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
WINDOW_SIZE = 5          # utterances per sliding window
BOUNDARY_THRESHOLD = 0.25  # cosine sim below this → topic break
MIN_SEGMENT_UTTERANCES = 3  # don't create segments shorter than this
TOP_KEYWORDS = 4         # keywords per topic label

# Common English stopwords (no NLTK dependency)
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "ought", "used", "it", "its", "this", "that", "these", "those", "i",
    "me", "my", "we", "our", "you", "your", "he", "she", "they", "them",
    "his", "her", "their", "what", "which", "who", "whom", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "same", "so", "than",
    "too", "very", "just", "also", "up", "out", "about", "into", "through",
    "during", "before", "after", "above", "below", "between", "then",
    "here", "there", "yeah", "okay", "ok", "um", "uh", "like", "know",
    "think", "right", "good", "going", "get", "got", "go", "yes", "no",
    "well", "actually", "really", "mean", "thing", "things", "look",
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class TopicSegment:
    segment_id: int
    label: str                    # e.g. "budget planning, Q3 targets"
    keywords: list[str]
    utterances: list[dict]        # full utterance dicts
    speakers: list[str]           # unique speakers in this segment
    start_sec: float
    end_sec: float
    duration_sec: float
    utterance_count: int


# ── NLP helpers ───────────────────────────────────────────────────────────────

def _tokenise(text: str) -> list[str]:
    """Lowercase, remove punctuation, split into meaningful words."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [w for w in text.split() if w not in STOPWORDS and len(w) > 2]


def _build_tfidf_vectors(
    windows: list[list[str]],
) -> list[dict[str, float]]:
    """
    Compute TF-IDF for each window's word bag.
    IDF is computed across all windows.
    """
    n = len(windows)
    if n == 0:
        return []

    # Document frequency
    df: dict[str, int] = defaultdict(int)
    tf_lists: list[Counter] = []

    for tokens in windows:
        tf = Counter(tokens)
        tf_lists.append(tf)
        for word in set(tokens):
            df[word] += 1

    vectors = []
    for tf in tf_lists:
        total = sum(tf.values()) or 1
        vec: dict[str, float] = {}
        for word, count in tf.items():
            tf_score = count / total
            idf_score = math.log((n + 1) / (df[word] + 1)) + 1
            vec[word] = tf_score * idf_score
        vectors.append(vec)

    return vectors


def _cosine_similarity(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    if not v1 or not v2:
        return 0.0

    dot = sum(v1.get(w, 0) * v2.get(w, 0) for w in v1)
    norm1 = math.sqrt(sum(x ** 2 for x in v1.values()))
    norm2 = math.sqrt(sum(x ** 2 for x in v2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot / (norm1 * norm2)


def _extract_keywords(utterances: list[dict], top_n: int = TOP_KEYWORDS) -> list[str]:
    """Extract the most informative keywords from a list of utterances."""
    all_tokens: list[str] = []
    for utt in utterances:
        all_tokens.extend(_tokenise(utt.get("text", "")))

    if not all_tokens:
        return ["general discussion"]

    freq = Counter(all_tokens)
    return [word for word, _ in freq.most_common(top_n)]


def _make_label(keywords: list[str]) -> str:
    if not keywords:
        return "General Discussion"
    # Title-case the top keywords joined
    return ", ".join(kw.replace("-", " ").title() for kw in keywords[:3])


# ── Main segmenter ────────────────────────────────────────────────────────────

def segment_topics(transcript: dict) -> list[TopicSegment]:
    """
    Segment a transcript into topic blocks.

    Args:
        transcript: Standard transcript dict with "utterances" list.

    Returns:
        Ordered list of TopicSegment objects.
    """
    utterances = transcript.get("utterances", [])

    if len(utterances) < WINDOW_SIZE * 2:
        log.info("Transcript too short for topic segmentation — returning single segment")
        keywords = _extract_keywords(utterances)
        start = utterances[0].get("start", 0) / 1000 if utterances else 0
        end = utterances[-1].get("end", 0) / 1000 if utterances else 0
        return [TopicSegment(
            segment_id=0,
            label=_make_label(keywords),
            keywords=keywords,
            utterances=utterances,
            speakers=list({u.get("speaker", "?") for u in utterances}),
            start_sec=start,
            end_sec=end,
            duration_sec=end - start,
            utterance_count=len(utterances),
        )]

    log.info(f"Topic segmentation: {len(utterances)} utterances, window={WINDOW_SIZE}")

    # Build overlapping windows of tokens
    windows: list[list[str]] = []
    for i in range(len(utterances) - WINDOW_SIZE + 1):
        window_utts = utterances[i: i + WINDOW_SIZE]
        tokens = []
        for utt in window_utts:
            tokens.extend(_tokenise(utt.get("text", "")))
        windows.append(tokens)

    # TF-IDF vectors for each window
    vectors = _build_tfidf_vectors(windows)

    # Compute similarity between adjacent windows
    similarities: list[float] = []
    for i in range(len(vectors) - 1):
        sim = _cosine_similarity(vectors[i], vectors[i + 1])
        similarities.append(sim)

    # Detect boundaries: low similarity = topic change
    # Boundary at position i means split AFTER utterance i + WINDOW_SIZE // 2
    boundaries: set[int] = set()
    for i, sim in enumerate(similarities):
        if sim < BOUNDARY_THRESHOLD:
            # Map window index back to utterance index
            boundary_utt = i + WINDOW_SIZE // 2
            boundaries.add(boundary_utt)

    log.info(f"Detected {len(boundaries)} raw boundaries")

    # Build segments, enforcing minimum length
    segments_raw: list[list[dict]] = []
    current: list[dict] = []

    for idx, utt in enumerate(utterances):
        current.append(utt)
        if idx in boundaries and len(current) >= MIN_SEGMENT_UTTERANCES:
            segments_raw.append(current)
            current = []

    if current:
        segments_raw.append(current)

    # Merge tiny trailing segments into previous
    segments: list[list[dict]] = []
    for seg in segments_raw:
        if segments and len(seg) < MIN_SEGMENT_UTTERANCES:
            segments[-1].extend(seg)
        else:
            segments.append(seg)

    # Convert to TopicSegment dataclasses
    result: list[TopicSegment] = []
    for idx, seg_utts in enumerate(segments):
        keywords = _extract_keywords(seg_utts)
        start = seg_utts[0].get("start", 0) / 1000
        end = seg_utts[-1].get("end", seg_utts[-1].get("start", 0)) / 1000
        speakers = list({u.get("speaker", "?") for u in seg_utts})

        result.append(TopicSegment(
            segment_id=idx,
            label=_make_label(keywords),
            keywords=keywords,
            utterances=seg_utts,
            speakers=sorted(speakers),
            start_sec=round(start, 1),
            end_sec=round(end, 1),
            duration_sec=round(end - start, 1),
            utterance_count=len(seg_utts),
        ))

    log.info(f"Topic segmentation complete: {len(result)} segments")
    for s in result:
        log.info(f"  [{s.segment_id}] {s.label!r} — {s.utterance_count} utterances, {s.duration_sec}s")

    return result


def segments_to_dict(segments: list[TopicSegment]) -> list[dict]:
    """Serialise TopicSegment list to JSON-safe dicts."""
    return [
        {
            "segment_id": s.segment_id,
            "label": s.label,
            "keywords": s.keywords,
            "speakers": s.speakers,
            "start_sec": s.start_sec,
            "end_sec": s.end_sec,
            "duration_sec": s.duration_sec,
            "utterance_count": s.utterance_count,
        }
        for s in segments
    ]
