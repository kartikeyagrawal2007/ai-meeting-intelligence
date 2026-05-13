from __future__ import annotations

from groq import Groq  # type: ignore[import-untyped]
from utils.config import GROQ_API_KEY, GROQ_MODEL
from utils.logger import get_logger
import json


log = get_logger(__name__)
client = Groq(api_key=GROQ_API_KEY)

# Maximum utterances to send for sentiment analysis (token budget guard)
MAX_SENTIMENT_UTTERANCES = 80
# Number of equal time windows to sample from (temporal stratification)
SENTIMENT_WINDOWS = 8

BATCH_SENTIMENT_PROMPT = """\
You are a sentiment analysis engine. Analyze the sentiment of each utterance below.

Return ONLY a valid JSON array — one object per utterance in the same order.
No explanation, no markdown.

Each object must have:
{{
  "sentiment": "positive" | "negative" | "neutral",
  "score": float between -1.0 and 1.0,
  "emotion": "neutral" | "happy" | "frustrated" | "confused" | "confident" | "anxious" | "angry",
  "energy": "high" | "medium" | "low",
  "flags": {{
    "is_frustrated": true | false,
    "is_confused": true | false,
    "is_agreeable": true | false,
    "is_decisive": true | false
  }}
}}

Utterances:
{utterances_text}
"""


def _sample_utterances_by_time(
    utterances: list,
    max_count: int,
    n_windows: int,
) -> tuple[list, list[int]]:
    """
    Stratified temporal sampling: divide the meeting timeline into
    `n_windows` equal time buckets and sample proportionally from each.

    Returns:
        sampled_utterances: the selected utterances (ordered by time)
        original_indices:   their positions in the original list (for mapping results back)
    """
    if len(utterances) <= max_count:
        return utterances, list(range(len(utterances)))

    # Prefer timestamp-based windows; fall back to index-based if no timestamps
    has_timestamps = all("start" in u for u in utterances)

    if has_timestamps:
        t_start = utterances[0]["start"]
        t_end = utterances[-1]["end"] if "end" in utterances[-1] else utterances[-1]["start"]
        duration = max(t_end - t_start, 1)
        window_size = duration / n_windows

        # Assign each utterance to a window
        buckets: list[list[int]] = [[] for _ in range(n_windows)]
        for idx, utt in enumerate(utterances):
            w = int((utt["start"] - t_start) / window_size)
            w = min(w, n_windows - 1)
            buckets[w].append(idx)
    else:
        # Fallback: index-based even split
        log.debug("No timestamps found — using index-based stratified sampling")
        bucket_size = max(len(utterances) // n_windows, 1)
        buckets = [
            list(range(i, min(i + bucket_size, len(utterances))))
            for i in range(0, len(utterances), bucket_size)
        ]

    # Allocate slots per window proportionally (at least 1 per non-empty window)
    non_empty = [b for b in buckets if b]
    per_window = max(1, max_count // max(len(non_empty), 1))

    selected_indices: list[int] = []
    for bucket in non_empty:
        # Distribute evenly inside the bucket
        step = max(1, len(bucket) // per_window)
        selected_indices.extend(bucket[::step][:per_window])

    # Trim if we overshot (rounding), preserve time order
    selected_indices = sorted(set(selected_indices))[:max_count]

    sampled = [utterances[i] for i in selected_indices]
    log.info(
        f"  Sentiment sampling: {len(utterances)} utterances → "
        f"{len(sampled)} sampled across {len(non_empty)} time windows"
    )
    return sampled, selected_indices


def analyze_sentiment(transcript: dict) -> dict:
    log.info("Analyzing sentiment (batch mode, temporal sampling)...")

    utterances = transcript.get("utterances", [])
    if not utterances:
        log.warning("No utterances found, skipping sentiment")
        return {}

    # ----------------------------------------------------------------
    # Smarter sampling: pick utterances spread across the full timeline
    # instead of just truncating at first 50
    # ----------------------------------------------------------------
    sampled_utterances, sampled_indices = _sample_utterances_by_time(
        utterances, MAX_SENTIMENT_UTTERANCES, SENTIMENT_WINDOWS
    )

    batch_size = 10
    all_results = []

    for batch_start in range(0, len(sampled_utterances), batch_size):
        batch = sampled_utterances[batch_start:batch_start + batch_size]

        # format batch as numbered list
        lines = []
        for i, utt in enumerate(batch):
            text = utt.get("text", "").strip()
            lines.append(f"{i+1}. [{utt.get('speaker')}]: {text}")

        utterances_text = "\n".join(lines)

        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{
                    "role": "user",
                    "content": BATCH_SENTIMENT_PROMPT.format(
                        utterances_text=utterances_text
                    )
                }],
                temperature=0.1,
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0]

            batch_results = json.loads(raw.strip())
            all_results.extend(batch_results)
            log.info(f"  Batch {batch_start//batch_size + 1}: {len(batch_results)} utterances analyzed")

        except Exception as e:
            log.warning(f"  Batch sentiment failed: {e}")
            # fill with neutral for failed batch
            for _ in batch:
                all_results.append({
                    "sentiment": "neutral",
                    "score": 0.0,
                    "emotion": "neutral",
                    "energy": "medium",
                    "flags": {
                        "is_frustrated": False,
                        "is_confused": False,
                        "is_agreeable": False,
                        "is_decisive": False
                    }
                })

    # Build timeline: map results back to the SAMPLED utterances (not all utterances)
    # sampled_utterances[i] corresponds to all_results[i], and maps to
    # utterances[sampled_indices[i]] in the original transcript.
    timeline = []
    speaker_sentiments = {}

    for i, utt in enumerate(sampled_utterances):
        if i >= len(all_results):
            break

        speaker = utt.get("speaker", "Unknown")
        start_sec = utt.get("start", 0) // 1000
        text = utt.get("text", "")
        result = all_results[i]

        timeline.append({
            "speaker": speaker,
            "start_sec": start_sec,
            "original_index": sampled_indices[i],  # preserve position in original transcript
            "text": text[:80] + "..." if len(text) > 80 else text,
            "sentiment": result.get("sentiment", "neutral"),
            "score": result.get("score", 0.0),
            "emotion": result.get("emotion", "neutral"),
            "energy": result.get("energy", "medium"),
            "flags": result.get("flags", {})
        })

        if speaker not in speaker_sentiments:
            speaker_sentiments[speaker] = {
                "scores": [],
                "emotions": [],
                "flags": {
                    "frustrated_count": 0,
                    "confused_count": 0,
                    "agreeable_count": 0,
                    "decisive_count": 0
                }
            }

        speaker_sentiments[speaker]["scores"].append(result.get("score", 0.0))
        speaker_sentiments[speaker]["emotions"].append(result.get("emotion", "neutral"))

        flags = result.get("flags", {})
        if flags.get("is_frustrated"):
            speaker_sentiments[speaker]["flags"]["frustrated_count"] += 1
        if flags.get("is_confused"):
            speaker_sentiments[speaker]["flags"]["confused_count"] += 1
        if flags.get("is_agreeable"):
            speaker_sentiments[speaker]["flags"]["agreeable_count"] += 1
        if flags.get("is_decisive"):
            speaker_sentiments[speaker]["flags"]["decisive_count"] += 1

    # compute speaker summary
    speaker_summary = {}
    for speaker, data in speaker_sentiments.items():
        scores = data["scores"]
        avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0

        if avg_score > 0.2:
            overall = "positive"
        elif avg_score < -0.2:
            overall = "negative"
        else:
            overall = "neutral"

        most_common_emotion = max(
            set(data["emotions"]),
            key=data["emotions"].count
        ) if data["emotions"] else "neutral"

        speaker_summary[speaker] = {
            "average_score": avg_score,
            "overall_sentiment": overall,
            "dominant_emotion": most_common_emotion,
            "utterance_count": len(scores),
            "flags": data["flags"]
        }

    log.info(f"Sentiment complete. {len(timeline)} utterances, {len(speaker_summary)} speakers.")

    return {
        "timeline": timeline,
        "speaker_summary": speaker_summary
    }