from groq import Groq
from utils.config import GROQ_API_KEY, GROQ_MODEL
from utils.logger import get_logger
import json

log = get_logger(__name__)
client = Groq(api_key=GROQ_API_KEY)

SENTIMENT_PROMPT = """\
You are a sentiment analysis engine for meeting transcripts.

Analyze the sentiment of this single utterance from a meeting.

Return ONLY valid JSON, no explanation, no markdown.

{{
  "sentiment": "positive" | "negative" | "neutral",
  "score": <float between -1.0 (very negative) and 1.0 (very positive)>,
  "emotion": "neutral" | "happy" | "frustrated" | "confused" | "confident" | "anxious" | "angry",
  "energy": "high" | "medium" | "low",
  "flags": {{
    "is_frustrated": true | false,
    "is_confused": true | false,
    "is_agreeable": true | false,
    "is_decisive": true | false
  }}
}}

Utterance:
{text}
"""

def analyze_utterance_sentiment(text: str) -> dict:
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": SENTIMENT_PROMPT.format(text=text)
            }],
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]

        return json.loads(raw.strip())

    except Exception as e:
        log.warning(f"Sentiment analysis failed for utterance: {e}")
        return {
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
        }

def analyze_sentiment(transcript: dict) -> dict:
    log.info("Analyzing sentiment...")

    utterances = transcript.get("utterances", [])
    if not utterances:
        log.warning("No utterances found, skipping sentiment")
        return {}

    # per utterance sentiment
    timeline = []
    speaker_sentiments = {}

    for utt in utterances:
        speaker = utt.get("speaker", "Unknown")
        text = utt.get("text", "").strip()
        start_sec = utt.get("start", 0) // 1000

        if not text:
            continue

        result = analyze_utterance_sentiment(text)

        timeline.append({
            "speaker": speaker,
            "start_sec": start_sec,
            "text": text[:80] + "..." if len(text) > 80 else text,
            "sentiment": result["sentiment"],
            "score": result["score"],
            "emotion": result["emotion"],
            "energy": result["energy"],
            "flags": result["flags"]
        })

        # accumulate per speaker
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

        speaker_sentiments[speaker]["scores"].append(result["score"])
        speaker_sentiments[speaker]["emotions"].append(result["emotion"])

        flags = result.get("flags", {})
        if flags.get("is_frustrated"):
            speaker_sentiments[speaker]["flags"]["frustrated_count"] += 1
        if flags.get("is_confused"):
            speaker_sentiments[speaker]["flags"]["confused_count"] += 1
        if flags.get("is_agreeable"):
            speaker_sentiments[speaker]["flags"]["agreeable_count"] += 1
        if flags.get("is_decisive"):
            speaker_sentiments[speaker]["flags"]["decisive_count"] += 1

    # compute per speaker summary
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

    log.info(f"Sentiment analysis complete for {len(speaker_summary)} speakers.")

    return {
        "timeline": timeline,
        "speaker_summary": speaker_summary
    }