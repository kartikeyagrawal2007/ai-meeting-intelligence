"""
utils/transliterate.py
────────────────────────────────────────────────────────────────────────
Devanagari to WhatsApp-style Hinglish Transliteration Utility.

Example:
  Input:  "कैसा रहेगा सर"
  Output: "kaisa rahega sir"
"""

import re
from utils.logger import get_logger

log = get_logger(__name__)

DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")

# Common Hindi WhatsApp-style Vocabulary Dictionary for instant 100% accuracy
WORD_DICT = {
    "कैसा": "kaisa", "कैसी": "kaisi", "कैसे": "kaise",
    "रहेगा": "rahega", "रहेगी": "rahegi", "रहेंगे": "rahenge",
    "सर": "sir", "मैडम": "madam", "जी": "ji", "हाँ": "haan", "नहीं": "nahin",
    "नमस्कार": "namaskar", "हेलो": "hello", "शुभम": "shubham", "संदीप": "sandeep",
    "बात": "baat", "कर": "kar", "रहा": "raha", "रही": "rahi", "रहे": "rahe", "हूँ": "hoon", "है": "hai", "हैं": "hain", "हो": "ho",
    "आपकी": "aapki", "आपका": "aapka", "आपके": "aapke", "आप": "aap", "हमारा": "hamara", "हमारी": "hamari", "हमारे": "hamare",
    "सोसाइटी": "society", "एप्लीकेशन": "application", "रजिस्ट्रेशन": "registration", "कॉल": "call", "सर्विस": "service",
    "कन्फर्म": "confirm", "बिल्डिंग": "building", "फ्लैट": "flat", "गेस्ट": "guest", "एंट्री": "entry", "सिक्योरिटी": "security",
    "मैनेजमेंट": "management", "डेमोंस्ट्रेशन": "demonstration", "प्रोडक्ट": "product", "मीटिंग": "meeting", "रिकॉर्डिंग": "recording",
    "गूगल": "google", "मीट": "meet", "लिंक": "link", "शेयर": "share", "थैंक्यू": "thank you", "सोमच": "so much",
    "एक": "ek", "दो": "do", "तीन": "teen", "चार": "chaar", "पांच": "paanch", "छह": "chhah", "सात": "saat", "आठ": "aath", "नौ": "nau", "दस": "das",
    "बार": "baar", "चेक": "check", "करना": "karna", "चाहते": "chahte", "चाहेंगे": "chahenge", "था": "tha", "थी": "thi", "थे": "the",
    "मेंटेनेंस": "maintenance", "कलेक्शन": "collection", "बिल": "bill", "जनरेशन": "generation", "कोई": "koi", "कुछ": "kuch",
    "कहाँ": "kahan", "पर": "par", "लोकेटेड": "located", "सेकंड": "second", "गेट": "gate", "नंबर": "number",
    "सेक्टर": "sector", "नवी": "navi", "मुंबई": "mumbai", "पिन": "pin", "कोड": "code", "ओके": "okay", "ठीक": "theek",
    "अगर": "agar", "मैं": "main", "आपको": "aapko", "बताऊँ": "bataoon", "तो": "to", "ब्रोकर": "broker", "बेसिकली": "basically",
    "तरीके": "tarike", "का": "ka", "की": "ki", "के": "ke", "प्रोवाइड": "provide", "करता": "karta", "विजिटर्स": "visitors",
    "डिलीवरी": "delivery", "बॉइज": "boys", "डिजिटल": "digital", "प्लेटफॉर्म": "platform", "थ्रू": "through",
    "इम्प्रूव": "improve", "अकाउंटिंग": "accounting", "मॉड्यूल": "module", "हेल्प": "help", "आउट": "out",
    "प्रोसेस": "process", "हैंडओवर": "handover", "विदाउट": "without", "आईडिया": "idea", "यूजफुल": "useful",
    "इम्प्लीमेंट": "implement", "रिक्वायरमेंट": "requirement", "अकॉर्डिंग": "according", "एक्सप्लेन": "explain",
    "कोटेशन": "quotation", "प्रॉपर": "proper", "नेगोशिएबल": "negotiable", "फिक्स": "fix", "बजट": "budget",
    "कांटेक्ट": "contact", "मेल": "mail", "आईडी": "id", "रिपीट": "repeat", "स्टार्ट": "start", "फाइन": "fine",
    "सेशन": "session", "इन्वाइट": "invite", "टाइम": "time", "दीजिये": "dejiye", "थैंक": "thank", "यू": "you",
    "अच्छा": "achha", "चलो": "chalo", "लोगो": "logo", "ने": "ne", "आगे": "aage", "पूछ": "pooch", "और": "aur", "किया": "kiya",
}

VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}

MATRAS = {
    "ा": "a", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ँ": "n", "ः": "h",
}

CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    "क्ष": "ksh", "त्र": "tr", "ज्ञ": "gya", "ड़": "r", "ढ़": "rh", "फ़": "f", "ज़": "z", "ग़": "g", "ख़": "kh",
}


def has_devanagari(text: str) -> bool:
    """Return True if text contains Devanagari characters."""
    return bool(DEVANAGARI_REGEX.search(text or ""))


def _transliterate_word(word: str) -> str:
    """Transliterate a single Devanagari word into Hinglish."""
    clean_w = re.sub(r"[^\u0900-\u097Fa-zA-Z0-9]", "", word)
    if clean_w in WORD_DICT:
        return WORD_DICT[clean_w]

    res = []
    i = 0
    n = len(word)

    while i < n:
        char = word[i]

        if not ('\u0900' <= char <= '\u097f'):
            res.append(char)
            i += 1
            continue

        two = word[i:i+2]
        if two in CONSONANTS:
            res.append(CONSONANTS[two])
            i += 2
            continue

        if char in VOWELS:
            res.append(VOWELS[char])
            i += 1
            continue

        if char in MATRAS:
            res.append(MATRAS[char])
            i += 1
            continue

        if char in CONSONANTS:
            base = CONSONANTS[char]
            next_char = word[i+1] if i + 1 < n else ''

            if next_char == '्':  # Halant
                res.append(base)
                i += 2
                continue
            elif next_char in MATRAS:
                res.append(base)
                i += 1
                continue
            elif next_char in CONSONANTS or next_char in VOWELS:
                res.append(base + 'a')
                i += 1
                continue
            else:
                res.append(base)
                i += 1
                continue

        res.append(char)
        i += 1

    return "".join(res)


def transliterate_devanagari_to_hinglish(text: str) -> str:
    """
    Transliterate Devanagari Hindi text to WhatsApp-style Hinglish.

    Example:
      Input:  "कैसा रहेगा सर"
      Output: "kaisa rahega sir"
    """
    if not text or not has_devanagari(text):
        return ""

    words = text.split(" ")
    out_words = []

    for w in words:
        if has_devanagari(w):
            out_words.append(_transliterate_word(w))
        else:
            out_words.append(w)

    return " ".join(out_words)


def attach_hinglish_to_transcript(transcript: dict) -> dict:
    """
    Attach 'hinglish' field to every utterance containing Devanagari text.
    """
    utterances = transcript.get("utterances", [])
    if not utterances:
        return transcript

    updated_utterances = []
    devanagari_count = 0

    for utt in utterances:
        new_utt = utt.copy()
        text = utt.get("text", "")
        if has_devanagari(text):
            hinglish = transliterate_devanagari_to_hinglish(text)
            if hinglish:
                new_utt["hinglish"] = hinglish
                devanagari_count += 1
        updated_utterances.append(new_utt)

    if devanagari_count > 0:
        log.info(f"Attached Hinglish transliteration to {devanagari_count} Devanagari utterances")

    result = transcript.copy()
    result["utterances"] = updated_utterances
    return result
