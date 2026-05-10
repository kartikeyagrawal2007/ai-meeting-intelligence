import time
import requests
from utils.config import ASSEMBLYAI_API_KEY, ASSEMBLYAI_BASE_URL
from utils.logger import get_logger

log = get_logger(__name__)

class AssemblyAIProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or ASSEMBLYAI_API_KEY
        self.base_url = ASSEMBLYAI_BASE_URL
        self.headers = {"authorization": self.api_key}
    
    def transcribe(self, audio_path: str) -> dict:
        log.info(f"Transcribing with AssemblyAI: {audio_path}")
        
        # Upload audio
        with open(audio_path, "rb") as f:
            upload_response = requests.post(
                self.base_url + "/v2/upload", 
                headers=self.headers, 
                data=f
            )
        audio_url = upload_response.json()["upload_url"]
        
        # Request transcription
        response = requests.post(
            self.base_url + "/v2/transcript",
            headers=self.headers,
            json={
                "audio_url": audio_url,
                "speech_models": ["universal-2"],
                "speaker_labels": True,
                "language_detection": True,
            }
        )
        response_data = response.json()
        if "error" in response_data:
            raise RuntimeError(f"Transcription request failed: {response_data['error']}")
        transcript_id = response_data["id"]
        
        # Poll for completion
        polling_url = f"{self.base_url}/v2/transcript/{transcript_id}"
        while True:
            result = requests.get(polling_url, headers=self.headers).json()
            if result["status"] == "completed":
                log.info("Transcription complete.")
                return result
            elif result["status"] == "error":
                raise RuntimeError(f"Transcription failed: {result['error']}")
            log.info("Polling transcription status...")
            time.sleep(3)
