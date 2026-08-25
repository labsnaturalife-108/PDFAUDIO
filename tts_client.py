import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from config import DEFAULT_TTS_URL, DEFAULT_GENERATION_PARAMS
from voice_manager import VoiceProfile

class FishAudioClient:
    def __init__(self, api_url: str = DEFAULT_TTS_URL, timeout: int = 300):
        self.api_url = api_url
        self.timeout = timeout

    def check_connection(self) -> bool:
        """Verifies if the Fish Audio S2 server is reachable."""
        try:
            # Check root or docs or options
            base_url = self.api_url.rsplit("/", 1)[0]
            resp = requests.get(base_url, timeout=3)
            return resp.status_code in [200, 404, 405]
        except Exception:
            try:
                # Try connecting via socket
                import socket
                from urllib.parse import urlparse
                parsed = urlparse(self.api_url)
                s = socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 8020), timeout=2)
                s.close()
                return True
            except Exception:
                return False

    def generate_chunk(
        self,
        text: str,
        voice: VoiceProfile,
        custom_params: Optional[Dict[str, Any]] = None,
        retries: int = 3,
        save_path: Optional[Path] = None
    ) -> bytes:
        """
        Sends generation request to Fish Audio S2 for a single chunk.
        Retries up to `retries` times on network/server errors.
        """
        params = DEFAULT_GENERATION_PARAMS.copy()
        if custom_params:
            params.update(custom_params)

        payload = {
            "text": text,
            "chunk_length": params.get("chunk_length", 300),
            "max_tokens": params.get("max_tokens", 2048),
            "temperature": params.get("temperature", 0.85),
            "top_p": params.get("top_p", 0.85),
            "top_k": params.get("top_k", 30),
            "speed": params.get("speed", 1.0),
            "instruct": params.get("instruct", ""),
            "references": [
                {
                    "audio": voice.get_audio_base64(),
                    "text": voice.text
                }
            ]
        }

        last_error = None
        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout
                )
                if response.status_code == 200 and len(response.content) > 0:
                    audio_bytes = response.content
                    if save_path:
                        save_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(save_path, "wb") as f:
                            f.write(audio_bytes)
                    return audio_bytes
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            except requests.RequestException as e:
                last_error = str(e)

            if attempt < retries:
                time.sleep(2 * attempt)

        raise RuntimeError(f"Ошибка Fish Audio после {retries} попыток: {last_error}")
