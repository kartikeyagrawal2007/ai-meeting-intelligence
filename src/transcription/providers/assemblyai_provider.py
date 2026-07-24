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

    def _http_request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """Execute HTTP request with automatic retry on transient network socket errors."""
        max_retries = 5
        delay = 3
        for attempt in range(max_retries):
            try:
                response = requests.request(method, url, headers=self.headers, timeout=120, **kwargs)
                if 400 <= response.status_code < 500:
                    # Client payload error (e.g. 400 Bad Request) — do not retry, extract explicit API error detail
                    err_detail = response.text
                    try:
                        err_json = response.json()
                        err_detail = err_json.get("error", response.text)
                    except Exception:
                        pass
                    raise RuntimeError(f"AssemblyAI API {response.status_code} Error: {err_detail}")
                response.raise_for_status()
                return response
            except RuntimeError:
                raise
            except (requests.exceptions.RequestException, ConnectionError, OSError) as err:
                if attempt == max_retries - 1:
                    log.error(f"HTTP request failed after {max_retries} attempts: {err}")
                    raise
                log.warning(
                    f"Network issue ({err}) during {method} {url}. "
                    f"Retrying in {delay}s ({attempt + 1}/{max_retries})..."
                )
                time.sleep(delay)
                delay = min(delay * 2, 15)

    def transcribe(self, audio_path: str, speakers_expected: int | None = None) -> dict:
        log.info(f"Transcribing with AssemblyAI: {audio_path}")

        # ── Upload audio ──────────────────────────────────────────────────────
        with open(audio_path, "rb") as f:
            upload_response = self._http_request_with_retry(
                "POST",
                self.base_url + "/v2/upload",
                data=f,
            )
        audio_url = upload_response.json()["upload_url"]

        # ── Build transcription request ───────────────────────────────────────
        # Note: AssemblyAI API v2 uses speech_models array (universal-3-5-pro, universal-2)
        payload: dict = {
            "audio_url":          audio_url,
            "speech_models":      ["universal-3-5-pro", "universal-2"],
            "speaker_labels":     True,
            "punctuate":          True,
            "format_text":        True,
            "disfluencies":       False,
            "language_detection": True,  # Auto-detect language (Hindi, English, etc.)
        }

        if speakers_expected is not None and speakers_expected > 0:
            payload["speakers_expected"] = speakers_expected
            log.info(f"  Hinting {speakers_expected} speakers to AssemblyAI")

        response = self._http_request_with_retry(
            "POST",
            self.base_url + "/v2/transcript",
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
            try:
                res = self._http_request_with_retry("GET", polling_url)
                result = res.json()
                status = result.get("status")
                if status == "completed":
                    n_utts = len(result.get("utterances") or [])
                    log.info(f"AssemblyAI transcription complete. {n_utts} utterances.")
                    return result
                elif status == "error":
                    raise RuntimeError(f"Transcription failed: {result.get('error')}")
            except RuntimeError:
                raise
            except Exception as e:
                log.warning(f"Polling error ({e}), retrying status check...")

            log.info(f"Polling transcription status… retrying in {poll_interval}s")
            time.sleep(poll_interval)
            poll_interval = min(poll_interval + 2, 10)
