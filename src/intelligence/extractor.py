import json
from groq import Groq
from intelligence.prompts import EXTRACTION_PROMPT
from transcription.formatter import utterances_to_text
from utils.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TEMPERATURE
from utils.logger import get_logger

log = get_logger(__name__)
client = Groq(api_key=GROQ_API_KEY)

CONFIDENCE_THRESHOLD = 0.75

def extract_intelligence(transcript: dict) -> dict:
    log.info("Extracting action items, decisions, and follow-ups...")
    
    # for long transcripts, only use first 100 utterances for extraction
    # to stay within token limits
    utterances = transcript.get("utterances", [])
    if len(utterances) > 100:
        log.info(f"  Long transcript ({len(utterances)} utterances), sampling first 100 for extraction")
        sampled = transcript.copy()
        sampled["utterances"] = utterances[:100]
        transcript_text = utterances_to_text(sampled)
    else:
        transcript_text = utterances_to_text(transcript)
    
    prompt = EXTRACTION_PROMPT.format(transcript_text=transcript_text)


    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=GROQ_TEMPERATURE,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]

    data = json.loads(raw.strip())

    # split into confirmed vs uncertain based on confidence
    confirmed_actions = []
    uncertain_actions = []

    for item in data.get("action_items", []):
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

    for item in data.get("decisions", []):
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
        "follow_ups": data.get("follow_ups", []),
        "open_questions": data.get("open_questions", []),
        "high_level_summary": data.get("high_level_summary", ""),
    }

    log.info(
        f"Extraction complete. "
        f"{len(confirmed_actions)} action items, "
        f"{len(uncertain_actions)} uncertain, "
        f"{len(confirmed_decisions)} decisions."
    )

    return result