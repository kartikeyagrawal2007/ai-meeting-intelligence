import time
import requests
from utils.config import ASSEMBLYAI_API_KEY, ASSEMBLYAI_BASE_URL
from utils.logger import get_logger

log = get_logger(__name__)


class AssemblyAIProvider:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or ASSEMBLYAI_API_KEY
        self.base_url = ASSEMBLYAI_BASE_URL
        self.headers = {"authorization": self.api_key}

    def transcribe(self, audio_path: str, speakers_expected: int | None = None) -> dict:
        log.info(f"Transcribing with AssemblyAI: {audio_path}")

        # ── Upload audio ──────────────────────────────────────────────────────
        with open(audio_path, "rb") as f:
            upload_response = requests.post(
                self.base_url + "/v2/upload",
                headers=self.headers,
                data=f,
            )
        upload_response.raise_for_status()
        audio_url = upload_response.json()["upload_url"]

        # ── Build transcription request ───────────────────────────────────────
        # NOTE: "speech_model" (singular) is the correct AssemblyAI field.
        # Using a list under "speech_models" was silently ignored by the API.
        payload: dict = {
            "audio_url":     audio_url,
            "speech_model":  "best",     # "nano" | "default" | "best"
            "speaker_labels": True,       # diarization
            "punctuate":     True,        # auto punctuation
            "format_text":   True,        # numbers/dates written naturally
            "disfluencies":  False,       # strip um/uh automatically
            "language_code": "en_us",     # skip language detection latency
        }

        if speakers_expected is not None:
            payload["speakers_expected"] = speakers_expected
            log.info(f"  Hinting {speakers_expected} speakers to AssemblyAI")

        response = requests.post(
            self.base_url + "/v2/transcript",
            headers=self.headers,
            json=payload,
        )
        response_data = response.json()
        if "error" in response_data:
            raise RuntimeError(f"Transcription request failed: {response_data['error']}")
        transcript_id = response_data["id"]

        # ── Poll for completion (exponential backoff up to 10s) ───────────────
        polling_url = f"{self.base_url}/v2/transcript/{transcript_id}"
        poll_interval = 3
        while True:
            result = requests.get(polling_url, headers=self.headers).json()
            if result["status"] == "completed":
                n_utts = len(result.get("utterances") or [])
                log.info(f"AssemblyAI transcription complete. {n_utts} utterances.")
                return result
            elif result["status"] == "error":
                raise RuntimeError(f"Transcription failed: {result['error']}")
            log.info(f"Polling transcription status… retrying in {poll_interval}s")
            time.sleep(poll_interval)
            poll_interval = min(poll_interval + 2, 10)
