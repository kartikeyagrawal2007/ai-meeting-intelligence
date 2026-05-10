import time
import requests
from utils.config import ASSEMBLYAI_API_KEY, ASSEMBLYAI_BASE_URL
from utils.logger import get_logger

log = get_logger(__name__)
HEADERS = {"authorization": ASSEMBLYAI_API_KEY}

def transcribe_audio(audio_path: str) -> dict:
    log.info(f"Transcribing: {audio_path}")

    with open(audio_path, "rb") as f:
        upload_response = requests.post(
            ASSEMBLYAI_BASE_URL + "/v2/upload", headers=HEADERS, data=f
        )
    audio_url = upload_response.json()["upload_url"]

    response = requests.post(
        ASSEMBLYAI_BASE_URL + "/v2/transcript",
        headers=HEADERS,
        json={
            "audio_url": audio_url,
            "speech_model": "universal-2",
            "speaker_labels": True,
            "language_detection": True,
        }
    )
    transcript_id = response.json()["id"]

    polling_url = f"{ASSEMBLYAI_BASE_URL}/v2/transcript/{transcript_id}"
    while True:
        result = requests.get(polling_url, headers=HEADERS).json()
        if result["status"] == "completed":
            log.info("Transcription complete.")
            return result
        elif result["status"] == "error":
            raise RuntimeError(f"Transcription failed: {result['error']}")
        log.info("Polling transcription status...")
        time.sleep(3)
