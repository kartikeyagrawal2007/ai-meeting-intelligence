import re
from utils.logger import get_logger

log = get_logger(__name__)

def split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences using punctuation and natural breaks.
    """
    # split on . ! ? followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    # filter out empty strings and very short fragments
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]

    return sentences

def smooth_adjacent_utterances(utterances: list[dict], max_gap_ms: int = 500) -> list[dict]:
    """
    Merge consecutive utterances from the SAME speaker if the pause between them is <= max_gap_ms.
    Eliminates micro-fragmentation caused by STT/VAD engine pauses.
    """
    if not utterances:
        return []

    smoothed = [utterances[0].copy()]

    for curr in utterances[1:]:
        prev = smoothed[-1]
        same_speaker = curr.get("speaker") == prev.get("speaker")
        gap_ms = curr.get("start", 0) - prev.get("end", 0)

        if same_speaker and gap_ms <= max_gap_ms:
            prev["text"] = f"{prev.get('text', '').strip()} {curr.get('text', '').strip()}".strip()
            prev["end"] = max(prev.get("end", 0), curr.get("end", 0))
        else:
            smoothed.append(curr.copy())

    return smoothed


def chunk_utterances(transcript: dict, max_words: int = 30) -> dict:
    """
    Split long utterances into sentence-level chunks while merging micro-fragmented turns.
    Preserves speaker, timestamps, and all original fields.
    """
    raw_utterances = transcript.get("utterances", [])
    if not raw_utterances:
        return transcript

    # Smooth micro-fragmented turns from the same speaker
    utterances = smooth_adjacent_utterances(raw_utterances, max_gap_ms=500)

    chunked = []

    for utt in utterances:
        text = utt.get("text", "").strip()
        word_count = len(text.split())

        # short utterance — keep as is
        if word_count <= max_words:
            chunked.append(utt)
            continue

        # long utterance — split into sentences
        sentences = split_into_sentences(text)

        # Merge chunks shorter than 4 words with the next chunk
        merged_sentences = []
        i = 0
        while i < len(sentences):
            s = sentences[i]
            while len(s.split()) < 4 and i + 1 < len(sentences):
                i += 1
                s += " " + sentences[i]
            merged_sentences.append(s)
            i += 1
        sentences = merged_sentences

        final_sentences = []
        for s in sentences:
            if len(s.split()) > max_words:
                words = s.split()
                for j in range(0, len(words), max_words):
                    final_sentences.append(" ".join(words[j:j+max_words]))
            else:
                final_sentences.append(s)
        sentences = final_sentences

        if not sentences:
            chunked.append(utt)
            continue

        log.info(
            f"  Chunking Speaker {utt.get('speaker')} utterance "
            f"({word_count} words → {len(sentences)} sentences)"
        )

        # estimate timestamps per sentence proportionally
        total_chars = len(text)
        utt_start = utt.get("start", 0)
        utt_end = utt.get("end", utt_start + word_count * 400)
        duration = utt_end - utt_start

        char_pos = 0
        for sentence in sentences:
            sentence_start = utt_start + int(
                (char_pos / total_chars) * duration
            )
            sentence_end = utt_start + int(
                ((char_pos + len(sentence)) / total_chars) * duration
            )

            chunk = utt.copy()
            chunk["text"] = sentence
            chunk["start"] = sentence_start
            chunk["end"] = sentence_end

            chunked.append(chunk)
            char_pos += len(sentence) + 1

    log.info(
        f"Chunking complete: {len(utterances)} utterances "
        f"→ {len(chunked)} chunks"
    )

    # sort chunks by timestamp to interleave them properly
    chunked = sorted(chunked, key=lambda c: c.get("start", 0))

    # rebuild transcript text
    result = transcript.copy()
    result["utterances"] = chunked
    result["text"] = " ".join(c["text"] for c in chunked)

    return result