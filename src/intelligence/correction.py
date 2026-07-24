import json
from groq import Groq
from utils.config import GROQ_API_KEY, GROQ_MODEL
from utils.logger import get_logger
from utils.token_tracker import record_usage

log = get_logger(__name__)
client = Groq(api_key=GROQ_API_KEY)


def resolve_speaker_names(transcript: dict) -> dict:
    """
    Scan transcript utterances for speaker self-introductions or direct callouts,
    and resolve anonymous speaker labels (e.g., Speaker A -> Rahul).
    """
    utterances = transcript.get("utterances", [])
    if not utterances:
        return transcript

    sample_text = "\n".join(
        f"{u.get('speaker', 'A')}: {u.get('text', '')}"
        for u in utterances[:50]
    )

    prompt = f"""Analyze this meeting transcript excerpt to detect the actual human names of the speakers.
Look for self-introductions (e.g., "Hi, I'm Rahul"), greetings ("Thanks Sarah"), or direct mentions.

Return a JSON object mapping each speaker label to their identified real first name (or keep the label if unknown).

Example output:
{{
  "speaker_map": {{
    "Speaker A": "Rahul",
    "Speaker B": "Sarah"
  }}
}}

Transcript excerpt:
{sample_text}"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        if response.usage:
            record_usage(response.usage.total_tokens, source="speaker_resolution")

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        speaker_map = data.get("speaker_map", {})

        valid_map = {
            k: v.strip()
            for k, v in speaker_map.items()
            if v and isinstance(v, str) and v.strip().lower() != k.strip().lower() and len(v.strip()) > 1
        }

        if valid_map:
            log.info(f"Resolved real speaker names: {valid_map}")
            updated_utts = []
            for utt in utterances:
                new_utt = utt.copy()
                curr_spk = utt.get("speaker", "")
                if curr_spk in valid_map:
                    new_utt["speaker"] = valid_map[curr_spk]
                updated_utts.append(new_utt)

            result = transcript.copy()
            result["utterances"] = updated_utts
            return result

    except Exception as e:
        log.warning(f"Speaker name resolution skipped: {e}")

    return transcript


def correct_transcript(transcript: dict) -> dict:
    log.info("Correcting transcript (batch mode + speaker name resolution)...")

    # Step 1: Resolve speaker names if present
    transcript = resolve_speaker_names(transcript)

    utterances = transcript.get("utterances", [])
    if not utterances:
        log.warning("No utterances found, skipping correction")
        return transcript

    # Separate short utterances (keep as-is) from long ones (correct)
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

    # Batch correct in groups of 20
    batch_size = 20
    for batch_start in range(0, len(to_correct), batch_size):
        batch = to_correct[batch_start:batch_start + batch_size]

        numbered = "\n".join(
            f"{j+1}. {utt['text']}"
            for j, (_, utt) in enumerate(batch)
        )

        prompt = f"""Fix these transcript segments. Remove filler words (um, uh, like, you know), fix false starts, fix punctuation and capitalization, and fix speech recognition errors.

Return a JSON object with a "corrected" array of strings in the exact same order.

Example output:
{{
  "corrected": [
    "So we need to finalize the budget.",
    "Yeah, I think that makes sense."
  ]
}}

Now correct these:
{numbered}"""

        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content.strip()

            if response.usage:
                record_usage(response.usage.total_tokens, source="correction")

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0]

            parsed = json.loads(raw.strip())
            corrected_texts = parsed.get("corrected", parsed if isinstance(parsed, list) else [])

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

    # Add skipped utterances back unchanged
    for orig_idx, orig_utt in to_skip:
        corrected_map[orig_idx] = orig_utt

    # Rebuild in original order
    all_corrected = [corrected_map[i] for i in range(len(utterances))]

    corrected_transcript = transcript.copy()
    corrected_transcript["utterances"] = all_corrected
    corrected_transcript["text"] = " ".join(
        utt["text"] for utt in all_corrected
    )

    log.info(f"Correction complete. {len(all_corrected)} utterances processed.")
    return corrected_transcript