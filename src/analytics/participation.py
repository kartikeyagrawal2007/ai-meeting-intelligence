from collections import defaultdict


def analyze_participation(transcript):
    """
    Analyze speaker participation metrics.

    Expected transcript format:
    {
        "utterances": [
            {
                "speaker": "A",
                "start": 1000,
                "end": 4000,
                "text": "Hello everyone"
            }
        ]
    }
    """

    speaker_stats = defaultdict(lambda: {
        "total_speaking_time": 0,
        "utterance_count": 0,
        "total_words": 0,
        "longest_streak": 0
    })

    total_meeting_time = 0

    for utt in transcript["utterances"]:
        speaker = utt["speaker"]

        duration = (utt["end"] - utt["start"]) / 1000
        word_count = len(utt["text"].split())

        speaker_stats[speaker]["total_speaking_time"] += duration
        speaker_stats[speaker]["utterance_count"] += 1
        speaker_stats[speaker]["total_words"] += word_count

        if duration > speaker_stats[speaker]["longest_streak"]:
            speaker_stats[speaker]["longest_streak"] = duration

        total_meeting_time += duration

    results = {}

    for speaker, stats in speaker_stats.items():

        speaking_share = (
            stats["total_speaking_time"] / total_meeting_time
        ) * 100 if total_meeting_time > 0 else 0

        avg_words = (
            stats["total_words"] / stats["utterance_count"]
        ) if stats["utterance_count"] > 0 else 0

        results[speaker] = {
            "speaking_time_seconds": round(stats["total_speaking_time"], 2),
            "speaking_share_percent": round(speaking_share, 2),
            "utterance_count": stats["utterance_count"],
            "average_words_per_utterance": round(avg_words, 2),
            "longest_speaking_streak_seconds": round(stats["longest_streak"], 2)
        }

    return results