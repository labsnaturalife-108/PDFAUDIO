import uuid
import time
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List
from config import OUTPUT_DIR, CACHE_DIR, DEFAULT_CHUNK_LENGTH, DEFAULT_PAUSE_DURATION, DEFAULT_AUDIO_FORMAT
from extractor import DocumentExtractor
from stress_dict import StressDictionary
from chunker import TextChunker
from voice_manager import VoiceManager, VoiceProfile
from tts_client import FishAudioClient
from audio_merger import AudioMerger

class PipelineProgress:
    def __init__(self, total_chunks: int = 0):
        self.session_id = str(uuid.uuid4())[:8]
        self.total_chunks = total_chunks
        self.current_chunk = 0
        self.status = "idle"  # idle, processing, merging, completed, error
        self.message = ""
        self.error = None
        self.chunk_statuses: List[Dict[str, Any]] = []
        self.output_file: Optional[Path] = None

class TextToSpeechPipeline:
    def __init__(
        self,
        dictionary: Optional[StressDictionary] = None,
        voice_manager: Optional[VoiceManager] = None,
        tts_client: Optional[FishAudioClient] = None
    ):
        self.dict = dictionary or StressDictionary()
        self.voice_mgr = voice_manager or VoiceManager()
        self.tts = tts_client or FishAudioClient()
        self.cancelled_sessions = set()

    def cancel(self, session_id: str):
        self.cancelled_sessions.add(session_id)

    def is_cancelled(self, session_id: str) -> bool:
        return session_id in self.cancelled_sessions

    def prepare_text(self, input_text_or_file: str | Path, max_chunk_len: int = DEFAULT_CHUNK_LENGTH) -> tuple[str, str, List[str]]:
        """
        Extracts text if file path, applies stress dictionary, and splits into chunks.
        Returns: (raw_text, stressed_text, chunks)
        """
        path = Path(input_text_or_file) if isinstance(input_text_or_file, str) and (input_text_or_file.endswith(".pdf") or input_text_or_file.endswith(".txt")) else None
        
        if path and path.exists():
            raw_text = DocumentExtractor.extract(path)
        else:
            raw_text = DocumentExtractor.clean_text(str(input_text_or_file))

        stressed_text = self.dict.apply(raw_text)
        chunks = TextChunker.split_into_chunks(stressed_text, max_chunk_len=max_chunk_len)
        return raw_text, stressed_text, chunks

    def process(
        self,
        text_or_chunks: str | List[str],
        voice: Optional[VoiceProfile] = None,
        voice_name: str = "default",
        output_name: Optional[str] = None,
        output_format: str = DEFAULT_AUDIO_FORMAT,
        max_chunk_len: int = DEFAULT_CHUNK_LENGTH,
        pause_duration: float = DEFAULT_PAUSE_DURATION,
        apply_loudnorm: bool = True,
        custom_tts_params: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[PipelineProgress], None]] = None,
        session_id: Optional[str] = None
    ) -> Path:
        """
        Runs the full text-to-speech generation pipeline.
        """
        active_voice = voice or self.voice_mgr.get_voice(voice_name)
        
        if isinstance(text_or_chunks, list):
            chunks = text_or_chunks
        else:
            _, _, chunks = self.prepare_text(text_or_chunks, max_chunk_len=max_chunk_len)

        if not chunks:
            raise ValueError("Нет текста для озвучки.")

        progress = PipelineProgress(total_chunks=len(chunks))
        if session_id:
            progress.session_id = session_id

        session_cache_dir = CACHE_DIR / progress.session_id
        session_cache_dir.mkdir(parents=True, exist_ok=True)

        progress.status = "processing"
        progress.chunk_statuses = [
            {"index": i, "text": chunk, "status": "pending", "audio_path": None}
            for i, chunk in enumerate(chunks)
        ]

        if progress_callback:
            progress_callback(progress)

        chunk_audio_files: List[Path] = []

        for i, chunk in enumerate(chunks):
            # Check if session was cancelled
            if self.is_cancelled(progress.session_id):
                progress.status = "cancelled"
                progress.message = "Генерация отменена пользователем."
                if progress_callback:
                    progress_callback(progress)
                return progress

            chunk_file = session_cache_dir / f"audio_chunk_{i:04d}.wav"
            progress.current_chunk = i + 1
            progress.chunk_statuses[i]["status"] = "generating"
            progress.message = f"Озвучка фрагмента {i+1} из {len(chunks)}..."
            
            if progress_callback:
                progress_callback(progress)

            try:
                # If cached chunk exists and valid, skip re-generation
                if chunk_file.exists() and chunk_file.stat().st_size > 1000:
                    pass
                else:
                    self.tts.generate_chunk(
                        text=chunk,
                        voice=active_voice,
                        custom_params=custom_tts_params,
                        save_path=chunk_file
                    )

                chunk_audio_files.append(chunk_file)
                progress.chunk_statuses[i]["status"] = "done"
                progress.chunk_statuses[i]["audio_path"] = str(chunk_file)
            except Exception as e:
                progress.chunk_statuses[i]["status"] = "error"
                progress.chunk_statuses[i]["error"] = str(e)
                progress.status = "error"
                progress.error = f"Ошибка на фрагменте {i+1}: {e}"
                if progress_callback:
                    progress_callback(progress)
                raise

            # Re-check cancellation immediately after chunk finishes
            if self.is_cancelled(progress.session_id):
                progress.status = "cancelled"
                progress.message = "Генерация отменена пользователем."
                if progress_callback:
                    progress_callback(progress)
                print(f"🛑 [Pipeline] Сессия {progress.session_id} немедленно остановлена после чанка {i+1}.")
                return progress

            if progress_callback:
                progress_callback(progress)

        # Check before merge
        if self.is_cancelled(progress.session_id):
            progress.status = "cancelled"
            progress.message = "Генерация отменена пользователем."
            if progress_callback:
                progress_callback(progress)
            return progress

        # Merge step
        progress.status = "merging"
        progress.message = "Склейка аудиодорожек и нормализация громкости (loudnorm)..."
        if progress_callback:
            progress_callback(progress)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = (output_name or f"audiobook_{timestamp}").replace(" ", "_")
        output_file = OUTPUT_DIR / f"{safe_name}.{output_format}"

        merged_path = AudioMerger.merge(
            chunk_files=chunk_audio_files,
            output_file=output_file,
            pause_duration=pause_duration,
            apply_loudnorm=apply_loudnorm,
            output_format=output_format
        )

        progress.status = "completed"
        progress.message = f"Озвучка успешно завершена! Файл сохранен в {merged_path.name}"
        progress.output_file = merged_path
        if progress_callback:
            progress_callback(progress)

        return merged_path
