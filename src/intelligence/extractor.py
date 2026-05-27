import json
# pyrefly: ignore [missing-import]
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
    
    # for long transcripts, do smart sampling instead of just first 100
    utterances = transcript.get("utterances", [])
    if len(utterances) > 100:
        log.info(f"  Long transcript ({len(utterances)} utterances), smart sampling (30 first, 40 middle, 30 last)")
        sampled = transcript.copy()
        first_30 = utterances[:30]
        last_30 = utterances[-30:]
        middle_utterances = utterances[30:-30]
        
        if len(middle_utterances) <= 40:
            middle_40 = middle_utterances
        else:
            step = len(middle_utterances) / 40.0
            middle_40 = [middle_utterances[int(i * step)] for i in range(40)]
            
        sampled["utterances"] = first_30 + middle_40 + last_30
        transcript_text = utterances_to_text(sampled)
    else:
        transcript_text = utterances_to_text(transcript)
    
    prompt = EXTRACTION_PROMPT.format(transcript_text=transcript_text)


    try:
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

    except Exception as e:
        log.warning(f"Extraction skipped — Groq API unavailable: {e}")
        return {
            "action_items": [],
            "uncertain_action_items": [],
            "decisions": [],
            "uncertain_decisions": [],
            "follow_ups": [],
            "open_questions": [],
            "summary": "Intelligence extraction unavailable (Groq API blocked or unreachable).",
        }

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
        "summary": data.get("summary", ""),
    }

    log.info(
        f"Extraction complete. "
        f"{len(confirmed_actions)} action items, "
        f"{len(uncertain_actions)} uncertain, "
        f"{len(confirmed_decisions)} decisions."
    )

    return result