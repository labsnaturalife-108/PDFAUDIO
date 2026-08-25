import base64
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from config import VOICES_DIR

DEFAULT_REFERENCE_TEXT = (
    "Случилось так, что Панду умер молодым, и его пятеро сыновей — "
    "Юдхиштхира, Бхима, Арджуна, Накула и Сахадева — остались на попечении Дхритараштры, "
    "который после смерти брата временно занял престол."
)

DEFAULT_SYSTEM_REF_PATH = Path("/Users/jeka/fish-audio-s2/voice/reference.wav")

class VoiceProfile:
    def __init__(self, name: str, audio_path: Path, text: str):
        self.name = name
        self.audio_path = audio_path
        self.text = text

    def get_audio_base64(self) -> str:
        if not self.audio_path.exists():
            raise FileNotFoundError(f"Файл эталонного голоса не найден: {self.audio_path}")
        with open(self.audio_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "audio_path": str(self.audio_path),
            "text": self.text,
            "exists": self.audio_path.exists()
        }


class VoiceManager:
    def __init__(self, voices_dir: Path = VOICES_DIR):
        self.voices_dir = voices_dir
        self.profiles_file = self.voices_dir / "profiles.json"
        self._init_defaults()

    def _init_defaults(self) -> None:
        if not self.profiles_file.exists():
            # Initial setup with default user voice reference
            profiles = {
                "default": {
                    "audio_path": str(DEFAULT_SYSTEM_REF_PATH),
                    "text": DEFAULT_REFERENCE_TEXT
                }
            }
            self._save_profiles(profiles)

    def _load_profiles(self) -> dict:
        if self.profiles_file.exists():
            with open(self.profiles_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_profiles(self, profiles: dict) -> None:
        with open(self.profiles_file, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

    def list_voices(self) -> List[VoiceProfile]:
        profiles_raw = self._load_profiles()
        result = []
        for name, data in profiles_raw.items():
            result.append(VoiceProfile(
                name=name,
                audio_path=Path(data["audio_path"]),
                text=data["text"]
            ))
        return result

    def get_voice(self, name: str = "default") -> VoiceProfile:
        profiles = self._load_profiles()
        if name in profiles:
            return VoiceProfile(
                name=name,
                audio_path=Path(profiles[name]["audio_path"]),
                text=profiles[name]["text"]
            )
        # If not found, return default
        return VoiceProfile(
            name="default",
            audio_path=DEFAULT_SYSTEM_REF_PATH,
            text=DEFAULT_REFERENCE_TEXT
        )

    def add_voice(self, name: str, audio_file_path: Path | str, text: str) -> VoiceProfile:
        src = Path(audio_file_path)
        dest_filename = f"{name}_{src.name}"
        dest = self.voices_dir / dest_filename
        if src != dest:
            shutil.copy2(src, dest)

        profiles = self._load_profiles()
        profiles[name] = {
            "audio_path": str(dest),
            "text": text
        }
        self._save_profiles(profiles)
        return VoiceProfile(name=name, audio_path=dest, text=text)

    def delete_voice(self, name: str) -> bool:
        if name == "default":
            return False
        profiles = self._load_profiles()
        if name in profiles:
            audio_path = Path(profiles[name]["audio_path"])
            if audio_path.exists() and audio_path.parent == self.voices_dir:
                audio_path.unlink()
            del profiles[name]
            self._save_profiles(profiles)
            return True
        return False
