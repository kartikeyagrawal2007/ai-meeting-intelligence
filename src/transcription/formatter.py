def format_transcript(transcript: dict) -> str:
    lines = []
    for utt in transcript.get("utterances", []):
        start_sec = utt["start"] // 1000
        timestamp = f"{start_sec // 60:02d}:{start_sec % 60:02d}"
        lines.append(f"[{timestamp}] Speaker {utt['speaker']}: {utt['text']}")
    return "\n".join(lines)

def utterances_to_text(transcript: dict) -> str:
    """Plain text for LLM prompts — no timestamps."""
    lines = []
    for utt in transcript.get("utterances", []):
        start_sec = utt["start"] // 1000
        timestamp = f"{start_sec // 60:02d}:{start_sec % 60:02d}"
        lines.append(f"[{timestamp}] Speaker {utt['speaker']}: {utt['text']}")
    return "\n".join(lines)
