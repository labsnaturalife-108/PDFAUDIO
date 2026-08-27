import os
import time
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List

class LumeanClient:
    """
    Client for Lumean Studio TTS API (https://lumean.app)
    Base URL: https://api.lumean.app/api/public
    Auth: Header 'X-API-KEY: <api_key>'
    """
    BASE_URL = "https://api.lumean.app/api/public"

    def __init__(self, api_key: str = "", timeout: int = 300):
        self.api_key = api_key.strip()
        self.timeout = timeout

    def check_connection(self) -> Dict[str, Any]:
        """Checks API key validity and connectivity."""
        if not self.api_key:
            return {"connected": False, "message": "API-ключ Lumean не указан"}
        
        try:
            resp = requests.get(
                f"{self.BASE_URL}/voices",
                headers={
                    "X-API-KEY": self.api_key,
                    "Accept": "application/json",
                    "User-Agent": "AudioBookStudio/1.0"
                },
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                voices_count = len(data) if isinstance(data, list) else len(data.get("data", []))
                return {"connected": True, "message": f"Lumean Онлайн ({voices_count} голосов доступно)"}
            elif resp.status_code == 403:
                err = resp.json().get("message", "Нет прав на выполнение действия")
                return {"connected": False, "message": f"Ошибка 403: {err}. Проверьте права API-ключа в кабинете lumean.app"}
            elif resp.status_code == 401:
                return {"connected": False, "message": "Неверный API-ключ Lumean"}
            else:
                return {"connected": False, "message": f"HTTP {resp.status_code}: {resp.text[:100]}"}
        except Exception as e:
            return {"connected": False, "message": f"Ошибка соединения: {str(e)}"}

    def fetch_voices(self) -> List[Dict[str, Any]]:
        """Retrieves list of available voices from Lumean."""
        if not self.api_key:
            return []

        try:
            resp = requests.get(
                f"{self.BASE_URL}/voices",
                headers={
                    "X-API-KEY": self.api_key,
                    "Accept": "application/json",
                    "User-Agent": "AudioBookStudio/1.0"
                },
                timeout=12
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("data", data.get("voices", []))
            return []
        except Exception:
            return []

    def generate_chunk(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        retries: int = 3,
        save_path: Optional[Path] = None
    ) -> bytes:
        """
        Synthesizes a single chunk using Lumean TTS.
        Creates an order on /api/public/orders and polls for completion.
        """
        if not self.api_key:
            raise ValueError("Не указан API-ключ Lumean.")

        payload = {
            "text": text,
            "voice_id": voice_id,
            "speed": speed
        }

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AudioBookStudio/1.0"
        }

        # Step 1: Create synthesis order / request
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(
                    f"{self.BASE_URL}/orders",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )

                if resp.status_code in [200, 201]:
                    res_data = resp.json()
                    # Check if audio is returned directly or as audio_url
                    if resp.headers.get("Content-Type", "").startswith("audio/"):
                        audio_bytes = resp.content
                        if save_path:
                            save_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(save_path, "wb") as f:
                                f.write(audio_bytes)
                        return audio_bytes

                    audio_url = None
                    if isinstance(res_data, dict):
                        audio_url = res_data.get("audio_url") or res_data.get("url") or (res_data.get("data") or {}).get("audio_url")
                        order_id = res_data.get("id") or res_data.get("order_id") or (res_data.get("data") or {}).get("id")

                        # If async order ID returned, poll order status
                        if not audio_url and order_id:
                            audio_url = self._poll_order(order_id, headers)

                    if audio_url:
                        # Download audio file
                        audio_resp = requests.get(audio_url, timeout=self.timeout)
                        if audio_resp.status_code == 200:
                            audio_bytes = audio_resp.content
                            if save_path:
                                save_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(save_path, "wb") as f:
                                    f.write(audio_bytes)
                            return audio_bytes

                    raise RuntimeError(f"Lumean не вернул ссылку на аудио: {res_data}")

                elif resp.status_code == 403:
                    err_msg = resp.json().get("message", "Нет прав на выполнение действия")
                    raise PermissionError(f"Ошибка прав Lumean (403): {err_msg}. Проверьте права API-ключа.")
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"

            except Exception as e:
                last_error = str(e)
                if isinstance(e, PermissionError):
                    raise

            if attempt < retries:
                time.sleep(2 * attempt)

        raise RuntimeError(f"Ошибка Lumean API после {retries} попыток: {last_error}")

    def _poll_order(self, order_id: str, headers: Dict[str, str], max_wait: int = 120) -> str:
        """Polls order completion on /api/public/orders/{id}"""
        start = time.time()
        while time.time() - start < max_wait:
            try:
                resp = requests.get(f"{self.BASE_URL}/orders/{order_id}", headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status") or (data.get("data") or {}).get("status")
                    audio_url = data.get("audio_url") or (data.get("data") or {}).get("audio_url") or data.get("url")
                    if status in ["completed", "done", "success"] and audio_url:
                        return audio_url
                    elif status in ["failed", "error"]:
                        raise RuntimeError(f"Генерация Lumean завершилась с ошибкой: {data}")
            except Exception as e:
                if "Генерация Lumean" in str(e):
                    raise
            time.sleep(1.5)
        raise TimeoutError("Превышено время ожидания готовности аудио в Lumean.")
