from groq import Groq
from utils.config import GROQ_API_KEY, GROQ_MODEL
from utils.logger import get_logger

log = get_logger(__name__)
client = Groq(api_key=GROQ_API_KEY)

CORRECTION_PROMPT = """\
You are a transcript correction engine. Fix the following transcript text.

Rules:
- Remove filler words: um, uh, like, you know, basically, literally
- Fix false starts: "I I was going" → "I was going"
- Fix obvious speech recognition errors based on context
- Fix punctuation and capitalization
- Do NOT change meaning or remove actual content
- Do NOT add information not in the original
- Return ONLY the corrected text, nothing else — no labels, no timestamps

Text to correct:
{text}
"""

def correct_transcript(transcript: dict) -> dict:
    log.info("Correcting transcript...")

    utterances = transcript.get("utterances", [])
    if not utterances:
        log.warning("No utterances found, skipping correction")
        return transcript

    corrected_utterances = []

    for utt in utterances:
        original_text = utt.get("text", "").strip()
        if not original_text:
            corrected_utterances.append(utt)
            continue

        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{
                    "role": "user",
                    "content": CORRECTION_PROMPT.format(text=original_text)
                }],
                temperature=0.1,
            )

            corrected_text = response.choices[0].message.content.strip()

            # make sure LLM didn't return a formatted line accidentally
            if "]: " in corrected_text:
                corrected_text = corrected_text.split("]: ", 1)[1].strip()

            if corrected_text and corrected_text != original_text:
                log.info(f"  Corrected utterance for Speaker {utt.get('speaker')}")

            updated = utt.copy()
            updated["text"] = corrected_text if corrected_text else original_text
            corrected_utterances.append(updated)

        except Exception as e:
            log.warning(f"  Correction failed for utterance, keeping original: {e}")
            corrected_utterances.append(utt)

    corrected_transcript = transcript.copy()
    corrected_transcript["utterances"] = corrected_utterances
    corrected_transcript["text"] = " ".join(
        utt["text"] for utt in corrected_utterances
    )

    log.info(f"Correction complete. {len(corrected_utterances)} utterances processed.")
    return corrected_transcript