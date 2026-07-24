import sys
import os
import concurrent.futures

from utils.chunker import chunk_utterances
from intelligence.sentiment import analyze_sentiment
from analytics.participation import analyze_participation
from analytics.interruptions import analyze_interruptions
from analytics.quality_score import compute_quality_score, format_quality_report
from audio.preprocess import preprocess_audio

from transcription.transcriber import transcribe_audio
from transcription.formatter import format_transcript

from intelligence.extractor import extract_intelligence
from intelligence.correction import correct_transcript
from intelligence.topic_segmenter import segment_topics, segments_to_dict

from output.recap import render_recap
from output.export_json import export_to_json

from utils.logger import get_logger

log = get_logger(__name__)


def analyze_meeting(
    audio_path: str,
    meeting_title: str = "Meeting",
    skip_preprocess: bool = False,
    skip_correction: bool = False,
    skip_sentiment: bool = False,
    provider: str = "assemblyai",
    speakers_expected: int | None = None,
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
    transcript = transcribe_audio(clean_path, provider=provider, speakers_expected=speakers_expected)

    # -----------------------------
    # Utterance chunking
    # -----------------------------
    transcript = chunk_utterances(transcript, max_words=30)

    # -----------------------------
    # Transcript correction
    # -----------------------------
    if skip_correction:
        log.info("Skipping transcript correction")
    else:
        transcript = correct_transcript(transcript)

    # -----------------------------
    # Participation analytics
    # -----------------------------
    participation_stats = analyze_participation(transcript)
    interruptions = analyze_interruptions(transcript)

    # -----------------------------
    # Format transcript
    # -----------------------------
    formatted = format_transcript(transcript)

    print("\n--- TRANSCRIPT ---")
    print(formatted)

    # -----------------------------
    # Print participation analytics
    # -----------------------------
    print("\n=== PARTICIPATION ANALYTICS ===")

    for speaker, stats in participation_stats.items():
        print(f"\nSpeaker {speaker}")
        print(f"  Speaking Time   : {stats['speaking_time_seconds']} sec")
        print(f"  Speaking Share  : {stats['speaking_share_percent']}%")
        print(f"  Utterances      : {stats['utterance_count']}")
        print(f"  Avg Words/Turn  : {stats['average_words_per_utterance']}")
        print(f"  Longest Streak  : {stats['longest_speaking_streak_seconds']} sec")

    # -----------------------------
    # Print interruption analytics
    # -----------------------------
    print("\n=== INTERRUPTION ANALYTICS ===")

    if interruptions:
        for item in interruptions[:5]:
            print(
                f"  {item['interrupter']} interrupted "
                f"{item['interrupted']} "
                f"({item['overlap_ms']} ms overlap)"
            )
    else:
        print("  No interruptions detected")

    # -----------------------------
    # Intelligence Extraction & Sentiment Analysis
    # (Running in parallel)
    # -----------------------------
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_intelligence = executor.submit(extract_intelligence, transcript)
        
        if skip_sentiment:
            log.info("Skipping sentiment analysis")
            future_sentiment = None
        else:
            future_sentiment = executor.submit(analyze_sentiment, transcript)

        intelligence = future_intelligence.result()
        sentiment = future_sentiment.result() if future_sentiment else {}

    if not skip_sentiment:
        print("\n=== SENTIMENT ANALYSIS ===")
        for speaker, summary in sentiment.get("speaker_summary", {}).items():
            print(f"\nSpeaker {speaker}")
            print(f"  Overall Sentiment : {summary['overall_sentiment']}")
            print(f"  Average Score     : {summary['average_score']}")
            print(f"  Dominant Emotion  : {summary['dominant_emotion']}")
            print(f"  Frustrated        : {summary['flags']['frustrated_count']} times")
            print(f"  Confused          : {summary['flags']['confused_count']} times")
            print(f"  Agreeable         : {summary['flags']['agreeable_count']} times")
            print(f"  Decisive          : {summary['flags']['decisive_count']} times")

    # -----------------------------
    # Meeting quality scoring
    # (pure analytics — no extra API calls)
    # -----------------------------
    quality = compute_quality_score(
        participation=participation_stats,
        interruptions=interruptions,
        sentiment=sentiment,
        intelligence=intelligence,
    )

    print(format_quality_report(quality))

    # -----------------------------
    # Topic segmentation & Recap
    # -----------------------------
    topics_dict = segments_to_dict(segment_topics(transcript))
    recap = render_recap(intelligence, meeting_title, topics=topics_dict)

    print("\n--- MEETING RECAP ---")
    print(recap)

    # -----------------------------
    # Save markdown recap
    # -----------------------------
    recap_output_path = audio_path.rsplit(".", 1)[0] + "_recap.md"

    with open(recap_output_path, "w") as f:
        f.write(recap)

    print(f"\nRecap saved to: {recap_output_path}")

    # -----------------------------
    # Export analytics JSON
    # -----------------------------
    analytics_output = {
        "meeting_title": meeting_title,
        "quality_score": {
            "total": quality.total,
            "rating": quality.rating,
            "sub_scores": {
                "participation": quality.participation_score,
                "sentiment": quality.sentiment_score,
                "decision_and_actions": quality.decision_score,
                "interruption_control": quality.interruption_score,
                "engagement_consistency": quality.engagement_score,
            },
            "breakdown": quality.breakdown,
            "diagnostics": quality.diagnostics,
        },
        "participation": participation_stats,
        "interruptions": interruptions,
        "sentiment": sentiment,
        "intelligence": intelligence,
    }

    os.makedirs("../outputs/analytics", exist_ok=True)
    analytics_output_path = "../outputs/analytics/meeting_analytics.json"

    export_to_json(analytics_output, analytics_output_path)
    print(f"Analytics saved to: {analytics_output_path}")

    return intelligence


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage: python main.py <audio_file> "
            "[meeting_title] [--skip-preprocess] [--skip-correction] "
            "[--skip-sentiment] [--groq] [--pyannote] [--speakers N]\n"
            "Providers: assemblyai (default), groq, pyannote"
        )
        sys.exit(1)

    audio_path = sys.argv[1]
    meeting_title = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "Meeting"
    skip_preprocess = "--skip-preprocess" in sys.argv
    skip_correction = "--skip-correction" in sys.argv
    skip_sentiment = "--skip-sentiment" in sys.argv
    
    if "--pyannote" in sys.argv:
        provider = "pyannote"
    elif "--groq" in sys.argv:
        provider = "groq"
    else:
        provider = "assemblyai"

    # Parse --speakers N
    speakers_expected: int | None = None
    for i, arg in enumerate(sys.argv):
        if arg == "--speakers" and i + 1 < len(sys.argv):
            try:
                speakers_expected = int(sys.argv[i + 1])
            except ValueError:
                print(f"Invalid --speakers value: {sys.argv[i+1]}")
                sys.exit(1)

    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        sys.exit(1)

    analyze_meeting(
        audio_path,
        meeting_title,
        skip_preprocess,
        skip_correction,
        skip_sentiment,
        provider,
        speakers_expected,
    )