import sys
import os

from audio.preprocess import preprocess_audio
from transcription.transcriber import transcribe_audio
from transcription.formatter import format_transcript
from intelligence.extractor import extract_intelligence
from output.recap import render_recap
from utils.logger import get_logger

log = get_logger(__name__)

def analyze_meeting(audio_path: str, meeting_title: str = "Meeting", skip_preprocess: bool = False) -> dict:
    clean_path = audio_path if skip_preprocess else preprocess_audio(audio_path)

    transcript = transcribe_audio(clean_path)

    formatted = format_transcript(transcript)
    log.info("\n--- TRANSCRIPT ---\n" + formatted)
    print("\n--- TRANSCRIPT ---")
    print(formatted)

    intelligence = extract_intelligence(transcript)

    recap = render_recap(intelligence, meeting_title)
    print("\n--- MEETING RECAP ---")
    print(recap)

    output_path = audio_path.rsplit(".", 1)[0] + "_recap.md"
    with open(output_path, "w") as f:
        f.write(recap)
    log.info(f"Recap saved to: {output_path}")

    return intelligence


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <audio_file> [meeting_title] [--skip-preprocess]")
        sys.exit(1)

    audio_path = sys.argv[1]
    meeting_title = sys.argv[2] if len(sys.argv) > 2 else "Meeting"
    skip_preprocess = "--skip-preprocess" in sys.argv

    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        sys.exit(1)

    analyze_meeting(audio_path, meeting_title, skip_preprocess)
