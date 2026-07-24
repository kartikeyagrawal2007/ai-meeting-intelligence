import json
# pyrefly: ignore [missing-import]
from groq import Groq
from intelligence.prompts import EXTRACTION_PROMPT
from transcription.formatter import utterances_to_text
from utils.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TEMPERATURE
from utils.logger import get_logger
from utils.token_tracker import record_usage

log = get_logger(__name__)
client = Groq(api_key=GROQ_API_KEY)

CONFIDENCE_THRESHOLD = 0.75
CHUNK_SIZE = 80
OVERLAP = 15


def extract_intelligence(transcript: dict) -> dict:
    log.info("Extracting action items, decisions, and follow-ups...")

    utterances = transcript.get("utterances", [])
    if not utterances:
        return {
            "action_items": [],
            "uncertain_action_items": [],
            "decisions": [],
            "uncertain_decisions": [],
            "follow_ups": [],
            "open_questions": [],
            "summary": "",
        }

    # ── Chunking for 100% transcript coverage ─────────────────────────────
    chunks = []
    if len(utterances) <= CHUNK_SIZE:
        chunks.append(utterances)
    else:
        step = CHUNK_SIZE - OVERLAP
        for start in range(0, len(utterances), step):
            chunk = utterances[start : start + CHUNK_SIZE]
            chunks.append(chunk)
            if start + CHUNK_SIZE >= len(utterances):
                break

    log.info(f"Processing transcript across {len(chunks)} full-coverage chunk(s)...")

    all_raw_data = []

    for idx, chunk_utts in enumerate(chunks):
        sub_transcript = transcript.copy()
        sub_transcript["utterances"] = chunk_utts
        transcript_text = utterances_to_text(sub_transcript)

        prompt = EXTRACTION_PROMPT.format(transcript_text=transcript_text)

        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=GROQ_TEMPERATURE,
                response_format={"type": "json_object"},
            )

            if response.usage:
                record_usage(response.usage.total_tokens, source="extraction")

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0]

            data = json.loads(raw.strip())
            all_raw_data.append(data)

        except Exception as e:
            log.warning(f"Extraction chunk {idx+1}/{len(chunks)} failed: {e}")

    if not all_raw_data:
        return {
            "action_items": [],
            "uncertain_action_items": [],
            "decisions": [],
            "uncertain_decisions": [],
            "follow_ups": [],
            "open_questions": [],
            "summary": "Intelligence extraction unavailable.",
        }

    # ── Deduplicate and merge results across all chunks ────────────────────
    all_actions = []
    seen_actions = set()
    for d in all_raw_data:
        for item in d.get("action_items", []):
            key = item.get("action", "").lower().strip()
            if key and key not in seen_actions:
                seen_actions.add(key)
                all_actions.append(item)

    all_decisions = []
    seen_decisions = set()
    for d in all_raw_data:
        for item in d.get("decisions", []):
            key = item.get("decision", "").lower().strip()
            if key and key not in seen_decisions:
                seen_decisions.add(key)
                all_decisions.append(item)

    all_followups = []
    seen_followups = set()
    for d in all_raw_data:
        for item in d.get("follow_ups", []):
            key = item.get("topic", "").lower().strip()
            if key and key not in seen_followups:
                seen_followups.add(key)
                all_followups.append(item)

    all_questions = []
    seen_questions = set()
    for d in all_raw_data:
        for item in d.get("open_questions", []):
            key = item.get("question", "").lower().strip()
            if key and key not in seen_questions:
                seen_questions.add(key)
                all_questions.append(item)

    summaries = [d.get("summary", "") for d in all_raw_data if d.get("summary")]
    final_summary = " ".join(summaries[:2]) if summaries else ""

    # ── Split into confirmed vs uncertain based on confidence ────────────
    confirmed_actions = []
    uncertain_actions = []

    for item in all_actions:
        confidence = item.get("confidence", 1.0)
        if confidence >= CONFIDENCE_THRESHOLD:
            confirmed_actions.append(item)
        else:
            uncertain_actions.append(item)
            log.info(
                f"  Low confidence action item flagged: "
                f"'{item.get('action')}' ({int(confidence*100)}%)"
            )

    confirmed_decisions = []
    uncertain_decisions = []

    for item in all_decisions:
        confidence = item.get("confidence", 1.0)
        if confidence >= CONFIDENCE_THRESHOLD:
            confirmed_decisions.append(item)
        else:
            uncertain_decisions.append(item)
            log.info(
                f"  Low confidence decision flagged: "
                f"'{item.get('decision')}' ({int(confidence*100)}%)"
            )

    result = {
        "action_items": confirmed_actions,
        "uncertain_action_items": uncertain_actions,
        "decisions": confirmed_decisions,
        "uncertain_decisions": uncertain_decisions,
        "follow_ups": all_followups,
        "open_questions": all_questions,
        "summary": final_summary,
    }

    log.info(
        f"Extraction complete (100% coverage). "
        f"{len(confirmed_actions)} action items, "
        f"{len(uncertain_actions)} uncertain, "
        f"{len(confirmed_decisions)} decisions."
    )

    return result