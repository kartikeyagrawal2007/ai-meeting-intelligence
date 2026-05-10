import json
from groq import Groq
from intelligence.prompts import EXTRACTION_PROMPT
from transcription.formatter import utterances_to_text
from utils.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TEMPERATURE
from utils.logger import get_logger

log = get_logger(__name__)
client = Groq(api_key=GROQ_API_KEY)

def extract_intelligence(transcript: dict) -> dict:
    log.info("Extracting action items, decisions, and follow-ups...")
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

    return json.loads(raw.strip())
