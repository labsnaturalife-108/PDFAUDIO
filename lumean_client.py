import os
import time
import json
import requests
import zipfile
import io
from pathlib import Path
from typing import Dict, Any, Optional, List

SETTINGS_PATH = Path("data/settings.json")

class LumeanTokenManager:
    """
    Manages access token and refresh token rotation with auto-persistence.
    """
    def __init__(self, settings_path: Path = SETTINGS_PATH):
        self.settings_path = settings_path

    def load_settings(self) -> Dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_tokens(self, access_token: str, refresh_token: str):
        settings = self.load_settings()
        settings["lumean_bearer_token"] = access_token
        settings["lumean_access_token"] = access_token
        settings["lumean_refresh_token"] = refresh_token
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def refresh(self) -> Optional[str]:
        """Exchanges refresh_token for a new access_token and refresh_token pair."""
        settings = self.load_settings()
        r_token = settings.get("lumean_refresh_token")
        if not r_token:
            return None

        try:
            resp = requests.post(
                "https://api.lumean.app/api/refresh",
                json={"refresh_token": r_token.strip()},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "AudioBookStudio/1.0"
                },
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                new_access = data.get("access_token")
                new_refresh = data.get("refresh_token")
                if new_access and new_refresh:
                    self.save_tokens(new_access, new_refresh)
                    return new_access
        except Exception:
            pass
        return None


class LumeanClient:
    """
    Client for Lumean Studio TTS API (https://lumean.app)
    Base URL: https://api.lumean.app/api
    Auth: Header 'X-API-KEY: <api_key>' and 'Authorization: Bearer <bearer_token>'
    """
    PUBLIC_BASE_URL = "https://api.lumean.app/api/public"
    API_BASE_URL = "https://api.lumean.app/api"

    def __init__(self, api_key: str = "", bearer_token: str = "", timeout: int = 300):
        self.api_key = api_key.strip()
        self.bearer_token = bearer_token.strip()
        self.timeout = timeout
        self._cached_template_id: Optional[str] = None
        self.token_manager = LumeanTokenManager()

    def check_connection(self) -> Dict[str, Any]:
        """Checks API key validity and connectivity."""
        if not self.api_key:
            return {"connected": False, "message": "API-ключ Lumean не указан"}
        
        try:
            resp = requests.get(
                f"{self.PUBLIC_BASE_URL}/templates",
                headers={
                    "X-API-KEY": self.api_key,
                    "Accept": "application/json",
                    "User-Agent": "AudioBookStudio/1.0"
                },
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                templates = data.get("data", [])
                t_count = len(templates)
                template_name = templates[0].get("name") if t_count > 0 else "Нет шаблонов"
                return {
                    "connected": True,
                    "message": f"Lumean Онлайн (Доступно шаблонов: {t_count}, активен: «{template_name}»)",
                    "templates": templates
                }
            elif resp.status_code == 403:
                err = resp.json().get("message", "Нет прав на выполнение действия")
                return {"connected": False, "message": f"Ошибка 403: {err}. Проверьте права API-ключа в кабинете lumean.app"}
            elif resp.status_code == 401:
                return {"connected": False, "message": "Неверный API-ключ Lumean"}
            else:
                return {"connected": False, "message": f"HTTP {resp.status_code}: {resp.text[:100]}"}
        except Exception as e:
            return {"connected": False, "message": f"Ошибка соединения: {str(e)}"}

    def fetch_templates(self) -> List[Dict[str, Any]]:
        """Retrieves list of user templates from Lumean."""
        if not self.api_key:
            return []

        try:
            resp = requests.get(
                f"{self.PUBLIC_BASE_URL}/templates",
                headers={
                    "X-API-KEY": self.api_key,
                    "Accept": "application/json",
                    "User-Agent": "AudioBookStudio/1.0"
                },
                timeout=12
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
            return []
        except Exception:
            return []

    def get_default_template_id(self) -> Optional[str]:
        """Gets or caches the default template ID."""
        if self._cached_template_id:
            return self._cached_template_id
        templates = self.fetch_templates()
        if templates:
            self._cached_template_id = templates[0].get("id")
            return self._cached_template_id
        return None

    def _get_current_bearer_token(self) -> str:
        """Gets current active Bearer token from settings or memory."""
        settings = self.token_manager.load_settings()
        return settings.get("lumean_bearer_token") or self.bearer_token

    def _request_archive_download_url(self, order_id: str) -> str:
        """
        Requests signed archive download URL. Automatically refreshes bearer token if expired.
        """
        token = self._get_current_bearer_token()

        for attempt in range(2):
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://lumean.app",
                "Referer": "https://lumean.app/"
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                headers["X-API-KEY"] = self.api_key

            try:
                arch_resp = requests.post(
                    f"{self.API_BASE_URL}/orders/{order_id}/archive",
                    json={"include_service_files": 1, "number_base": 1, "number_padding": 3},
                    headers=archive_headers if 'archive_headers' in locals() else headers,
                    timeout=30
                )

                if arch_resp.status_code == 200:
                    url = arch_resp.json().get("data", {}).get("url")
                    if url:
                        return url
                elif arch_resp.status_code == 401:
                    # Token expired -> automatically refresh
                    new_token = self.token_manager.refresh()
                    if new_token:
                        token = new_token
                        self.bearer_token = new_token
                        continue
                    else:
                        raise PermissionError("Сессия Lumean истекла. Пожалуйста, обновите refresh_token в настройках.")
                else:
                    time.sleep(2)
            except PermissionError:
                raise
            except Exception as e:
                time.sleep(2)

        raise RuntimeError(f"Не удалось получить ссылку на скачивание архива для заказа {order_id}")

    def generate_chunk(
        self,
        text: str,
        voice_id: Optional[str] = None,
        template_id: Optional[str] = None,
        speed: float = 1.0,
        save_path: Optional[Path] = None
    ) -> bytes:
        """
        Synthesizes a chunk using Lumean TTS.
        1. Creates order via /api/public/orders (STRICTLY ONCE, NO DUPLICATE ORDERS).
        2. Polls order until finished.
        3. Requests signed archive download link (with auto-refreshing token).
        4. Downloads zip and extracts the clean MP3 audio.
        """
        if not self.api_key:
            raise ValueError("Не указан API-ключ Lumean.")

        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Текст для озвучки пуст.")

        # Ensure template_id is resolved
        active_template_id = template_id or self.get_default_template_id()
        if not active_template_id:
            raise ValueError("Не найден активный шаблон в аккаунте Lumean. Создайте шаблон в кабинете lumean.app.")

        payload: Dict[str, Any] = {
            "template_id": active_template_id,
            "input_text": clean_text
        }

        if voice_id and voice_id.strip():
            payload["voice_id"] = voice_id.strip()
            payload["config"] = {
                "tts_settings": {
                    "voice_id": voice_id.strip(),
                    "voice_settings": {
                        "speed": speed
                    }
                }
            }

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AudioBookStudio/1.0"
        }

        # 1. Create order STRICTLY ONCE (No duplicate orders / No token waste)
        try:
            resp = requests.post(
                f"{self.PUBLIC_BASE_URL}/orders",
                json=payload,
                headers=headers,
                timeout=30
            )
        except Exception as e:
            raise RuntimeError(f"Ошибка сети при отправке заказа в Lumean: {e}")

        if resp.status_code not in [200, 201]:
            if resp.status_code == 422:
                val_err = resp.json().get("errors", {})
                raise ValueError(f"Ошибка валидации Lumean: {val_err}")
            elif resp.status_code == 403:
                err_msg = resp.json().get("message", "Нет прав на выполнение действия")
                raise PermissionError(f"Ошибка прав Lumean (403): {err_msg}")
            else:
                raise RuntimeError(f"Lumean API вернул ошибку {resp.status_code}: {resp.text[:200]}")

        res_data = resp.json().get("data", {})
        order_id = res_data.get("id")
        if not order_id:
            raise RuntimeError(f"Lumean не вернул ID созданного заказа: {resp.text[:200]}")

        # 2. Poll order until finished (Wait for audio synthesis)
        self._poll_order(order_id, headers)

        # 3. Request signed archive download link (with auto-token refresh)
        download_url = self._request_archive_download_url(order_id)

        # 4. Download zip and extract MP3
        zip_resp = requests.get(download_url, timeout=self.timeout)
        if zip_resp.status_code != 200 or len(zip_resp.content) == 0:
            raise RuntimeError(f"Ошибка загрузки архива ({zip_resp.status_code})")

        mp3_bytes = self._extract_mp3_from_zip(zip_resp.content)
        if not mp3_bytes:
            raise RuntimeError("В скачанном архиве Lumean не найден MP3 аудиофайл.")

        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(mp3_bytes)

        return mp3_bytes

    def _poll_order(self, order_id: str, headers: Dict[str, str], max_wait: int = 180):
        """Polls order completion on /api/public/orders/{id}"""
        start = time.time()
        while time.time() - start < max_wait:
            try:
                resp = requests.get(f"{self.PUBLIC_BASE_URL}/orders/{order_id}", headers=headers, timeout=12)
                if resp.status_code == 200:
                    order = resp.json().get("data", {})
                    status = order.get("status")

                    if status in ["completed", "done", "success"]:
                        return
                    elif status in ["failed", "error"]:
                        failure_reason = order.get("failure_reason") or "Неизвестная ошибка синтеза"
                        raise RuntimeError(f"Заказ в Lumean завершился с ошибкой: {failure_reason}")
            except Exception as e:
                if "Заказ в Lumean" in str(e):
                    raise
            time.sleep(2.0)

        raise TimeoutError("Превышено время ожидания готовности аудио в Lumean.")

    @staticmethod
    def _extract_mp3_from_zip(zip_bytes: bytes) -> Optional[bytes]:
        """Extracts first .mp3 file from zip bytes."""
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for filename in zf.namelist():
                    if filename.lower().endswith(".mp3"):
                        return zf.read(filename)
        except Exception:
            return None
        return None
