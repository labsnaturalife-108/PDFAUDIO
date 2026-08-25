import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VOICES_DIR = DATA_DIR / "voices"
DICTIONARIES_DIR = DATA_DIR / "dictionaries"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / "temp_cache"

for directory in [DATA_DIR, VOICES_DIR, DICTIONARIES_DIR, OUTPUT_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Default TTS Settings
DEFAULT_TTS_URL = os.getenv("FISH_AUDIO_URL", "http://127.0.0.1:8020/generate")
DEFAULT_CHUNK_LENGTH = 1000  # Max chars per sentence chunk
DEFAULT_PAUSE_DURATION = 0.6  # Seconds between chunks
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_AUDIO_FORMAT = "wav"  # wav or mp3

# Fish Audio Model Hyperparameters
DEFAULT_GENERATION_PARAMS = {
    "chunk_length": 300,
    "max_tokens": 2048,
    "temperature": 0.85,
    "top_p": 0.85,
    "top_k": 30,
    "speed": 1.0,
    "instruct": (
        "Read expressively like a professional audiobook narrator. "
        "Use vivid intonation, emotional depth, and natural pauses. "
        "Strictly pronounce Russian 'е' as 'Е' (E/EH) and 'ё' as 'Ё' (YO). "
        "Never pronounce 'е' as 'ё' or 'о' unless written with two dots explicitly."
    )
}

# FFmpeg normalization
LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
