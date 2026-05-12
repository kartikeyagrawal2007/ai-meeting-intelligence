import json
from groq import Groq
from utils.config import GROQ_API_KEY, GROQ_MODEL
from utils.logger import get_logger

log = get_logger(__name__)
client = Groq(api_key=GROQ_API_KEY)


def correct_transcript(transcript: dict) -> dict:
    log.info("Correcting transcript (batch mode)...")

    utterances = transcript.get("utterances", [])
    if not utterances:
        log.warning("No utterances found, skipping correction")
        return transcript

    # separate short utterances (keep as-is) from long ones (correct)
    to_correct = []
    to_skip = []

    for i, utt in enumerate(utterances):
        text = utt.get("text", "").strip()
        if len(text.split()) < 8:
            to_skip.append((i, utt))
        else:
            to_correct.append((i, utt))

    log.info(f"  {len(to_correct)} utterances to correct, {len(to_skip)} skipped (too short)")

    corrected_map = {}

    # batch correct in groups of 20
    batch_size = 20
    for batch_start in range(0, len(to_correct), batch_size):
        batch = to_correct[batch_start:batch_start + batch_size]

        numbered = "\n".join(
            f"{j+1}. {utt['text']}"
            for j, (_, utt) in enumerate(batch)
        )

        prompt = f"""Fix these transcript segments. Remove filler words (um, uh, like, you know), fix false starts, fix punctuation and capitalization, fix obvious speech recognition errors.

Return ONLY a JSON array of corrected strings in the same order. No explanation, no markdown.

Example input:
1. um so we we need to finalize the the budget
2. yeah i think uh that makes sense

Example output:
["So we need to finalize the budget.", "Yeah, I think that makes sense."]

Now correct these:
{numbered}"""

        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0]

            corrected_texts = json.loads(raw.strip())

            for j, (orig_idx, orig_utt) in enumerate(batch):
                if j < len(corrected_texts):
                    updated = orig_utt.copy()
                    corrected = corrected_texts[j]
                    if isinstance(corrected, str) and corrected.strip():
                        updated["text"] = corrected.strip()
                    corrected_map[orig_idx] = updated
                else:
                    corrected_map[orig_idx] = orig_utt

            log.info(f"  Batch {batch_start//batch_size + 1}: corrected {len(batch)} utterances")

        except Exception as e:
            log.warning(f"  Batch correction failed: {e}, keeping originals")
            for orig_idx, orig_utt in batch:
                corrected_map[orig_idx] = orig_utt

    # add skipped utterances back unchanged
    for orig_idx, orig_utt in to_skip:
        corrected_map[orig_idx] = orig_utt

    # rebuild in original order
    all_corrected = [corrected_map[i] for i in range(len(utterances))]

    corrected_transcript = transcript.copy()
    corrected_transcript["utterances"] = all_corrected
    corrected_transcript["text"] = " ".join(
        utt["text"] for utt in all_corrected
    )

    log.info(f"Correction complete. {len(all_corrected)} utterances processed.")
    return corrected_transcript