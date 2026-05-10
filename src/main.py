import sys
import os

from analytics.participation import analyze_participation
from analytics.interruptions import analyze_interruptions
from audio.preprocess import preprocess_audio

from transcription.transcriber import transcribe_audio
from transcription.formatter import format_transcript

from intelligence.extractor import extract_intelligence

from output.recap import render_recap
from output.export_json import export_to_json

from utils.logger import get_logger

log = get_logger(__name__)


def analyze_meeting(
    audio_path: str,
    meeting_title: str = "Meeting",
    skip_preprocess: bool = False
) -> dict:

    # -----------------------------
    # Audio preprocessing
    # -----------------------------
    clean_path = (
        audio_path
        if skip_preprocess
        else preprocess_audio(audio_path)
    )

    # -----------------------------
    # Transcription
    # -----------------------------
    transcript = transcribe_audio(clean_path)

    # -----------------------------
    # Participation analytics
    # -----------------------------
    participation_stats = analyze_participation(transcript)
    interruptions = analyze_interruptions(transcript)

    # -----------------------------
    # Format transcript
    # -----------------------------
    formatted = format_transcript(transcript)

    log.info("\n--- TRANSCRIPT ---\n" + formatted)

    print("\n--- TRANSCRIPT ---")
    print(formatted)

    # -----------------------------
    # Print participation analytics
    # -----------------------------
    print("\n=== PARTICIPATION ANALYTICS ===")

    for speaker, stats in participation_stats.items():

        print(f"\nSpeaker {speaker}")
        print(f"Speaking Time: {stats['speaking_time_seconds']} sec")
        print(f"Speaking Share: {stats['speaking_share_percent']}%")
        print(f"Utterances: {stats['utterance_count']}")
        print(f"Avg Words/Utterance: {stats['average_words_per_utterance']}")
        print(f"Longest Streak: {stats['longest_speaking_streak_seconds']} sec")

    print("\n=== INTERRUPTION ANALYTICS ===")

    if interruptions:
        for item in interruptions[:5]:
            print(
                f"{item['interrupter']} interrupted "
                f"{item['interrupted']} "
                f"({item['overlap_ms']} ms overlap)"
            )
    else:
        print("No interruptions detected")

    # -----------------------------
    # Intelligence extraction
    # -----------------------------
    intelligence = extract_intelligence(transcript)

    # -----------------------------
    # Generate recap
    # -----------------------------
    recap = render_recap(intelligence, meeting_title)

    print("\n--- MEETING RECAP ---")
    print(recap)

    # -----------------------------
    # Save markdown recap
    # -----------------------------
    recap_output_path = (
        audio_path.rsplit(".", 1)[0] + "_recap.md"
    )

    with open(recap_output_path, "w") as f:
        f.write(recap)

    log.info(f"Recap saved to: {recap_output_path}")

    # -----------------------------
    # Export analytics JSON
    # -----------------------------
    analytics_output = {
        "participation": participation_stats
    }

    analytics_output_path = (
        "../outputs/analytics/meeting_analytics.json"
    )

    export_to_json(
        analytics_output,
        analytics_output_path
    )

    return intelligence


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage: python main.py <audio_file> "
            "[meeting_title] [--skip-preprocess]"
        )
        sys.exit(1)

    audio_path = sys.argv[1]

    meeting_title = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "Meeting"
    )

    skip_preprocess = "--skip-preprocess" in sys.argv

    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        sys.exit(1)

    analyze_meeting(
        audio_path,
        meeting_title,
        skip_preprocess
    )