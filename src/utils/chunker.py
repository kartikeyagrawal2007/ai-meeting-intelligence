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

def chunk_utterances(transcript: dict, max_words: int = 30) -> dict:
    """
    Split long utterances into sentence-level chunks.
    Preserves speaker, timestamps, and all original fields.
    
    Any utterance longer than max_words gets split into sentences.
    Short utterances are kept as-is.
    """
    utterances = transcript.get("utterances", [])
    if not utterances:
        return transcript

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

        if len(sentences) <= 1:
            # can't split further, keep as is
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

    # rebuild transcript text
    result = transcript.copy()
    result["utterances"] = chunked
    result["text"] = " ".join(c["text"] for c in chunked)

    return result