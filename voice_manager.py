import base64
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from config import VOICES_DIR, DEFAULT_PAUSE_DURATION

DEFAULT_REFERENCE_TEXT = (
    "Случилось так, что Панду умер молодым, и его пятеро сыновей — "
    "Юдхиштхира, Бхима, Арджуна, Накула и Сахадева — остались на попечении Дхритараштры, "
    "который после смерти брата временно занял престол."
)

DEFAULT_SYSTEM_REF_PATH = Path("/Users/jeka/fish-audio-s2/voice/reference.wav")

class VoiceProfile:
    def __init__(
        self,
        name: str,
        audio_path: Path,
        text: str,
        speed: float = 1.0,
        pause_duration: float = DEFAULT_PAUSE_DURATION,
        temperature: float = 0.88,
        instruct: Optional[str] = None
    ):
        self.name = name
        self.audio_path = audio_path
        self.text = text
        self.speed = speed
        self.pause_duration = pause_duration
        self.temperature = temperature
        self.instruct = instruct

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
            "exists": self.audio_path.exists(),
            "speed": self.speed,
            "pause_duration": self.pause_duration,
            "temperature": self.temperature,
            "instruct": self.instruct
        }


class VoiceManager:
    def __init__(self, voices_dir: Path = VOICES_DIR):
        self.voices_dir = voices_dir
        self.profiles_file = self.voices_dir / "profiles.json"
        self._init_defaults()

    def _init_defaults(self) -> None:
        if not self.profiles_file.exists():
            profiles = {
                "default": {
                    "audio_path": str(DEFAULT_SYSTEM_REF_PATH),
                    "text": DEFAULT_REFERENCE_TEXT,
                    "speed": 1.0,
                    "pause_duration": DEFAULT_PAUSE_DURATION,
                    "temperature": 0.88,
                    "instruct": None
                }
            }
            self._save_profiles(profiles)

    def _load_profiles(self) -> dict:
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading voice profiles: {e}")
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
                audio_path=Path(data.get("audio_path", "")),
                text=data.get("text", ""),
                speed=float(data.get("speed", 1.0)),
                pause_duration=float(data.get("pause_duration", DEFAULT_PAUSE_DURATION)),
                temperature=float(data.get("temperature", 0.88)),
                instruct=data.get("instruct")
            ))
        return result

    def get_voice(self, name: str = "default") -> VoiceProfile:
        profiles = self._load_profiles()
        if name in profiles:
            data = profiles[name]
            return VoiceProfile(
                name=name,
                audio_path=Path(data.get("audio_path", "")),
                text=data.get("text", ""),
                speed=float(data.get("speed", 1.0)),
                pause_duration=float(data.get("pause_duration", DEFAULT_PAUSE_DURATION)),
                temperature=float(data.get("temperature", 0.88)),
                instruct=data.get("instruct")
            )
        # If not found, return default
        return VoiceProfile(
            name="default",
            audio_path=DEFAULT_SYSTEM_REF_PATH,
            text=DEFAULT_REFERENCE_TEXT,
            speed=1.0,
            pause_duration=DEFAULT_PAUSE_DURATION,
            temperature=0.88,
            instruct=None
        )

    def update_voice_settings(
        self,
        name: str,
        speed: float,
        pause_duration: float,
        temperature: float,
        instruct: Optional[str] = None
    ) -> VoiceProfile:
        profiles = self._load_profiles()
        if name not in profiles:
            if name == "default":
                profiles["default"] = {
                    "audio_path": str(DEFAULT_SYSTEM_REF_PATH),
                    "text": DEFAULT_REFERENCE_TEXT
                }
            else:
                raise ValueError(f"Голос '{name}' не найден")

        profiles[name]["speed"] = float(speed)
        profiles[name]["pause_duration"] = float(pause_duration)
        profiles[name]["temperature"] = float(temperature)
        profiles[name]["instruct"] = instruct.strip() if (instruct and instruct.strip()) else None

        self._save_profiles(profiles)
        return self.get_voice(name)

    def add_voice(
        self,
        name: str,
        audio_file_path: Path | str,
        text: str,
        speed: float = 1.0,
        pause_duration: float = DEFAULT_PAUSE_DURATION,
        temperature: float = 0.88,
        instruct: Optional[str] = None
    ) -> VoiceProfile:
        src = Path(audio_file_path)
        dest_filename = f"{name}_{src.name}"
        dest = self.voices_dir / dest_filename
        if src != dest:
            shutil.copy2(src, dest)

        profiles = self._load_profiles()
        profiles[name] = {
            "audio_path": str(dest),
            "text": text,
            "speed": float(speed),
            "pause_duration": float(pause_duration),
            "temperature": float(temperature),
            "instruct": instruct
        }
        self._save_profiles(profiles)
        return VoiceProfile(
            name=name,
            audio_path=dest,
            text=text,
            speed=speed,
            pause_duration=pause_duration,
            temperature=temperature,
            instruct=instruct
        )

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
