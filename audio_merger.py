import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional
from config import LOUDNORM_FILTER

class AudioMerger:
    @staticmethod
    def probe_audio(file_path: Path) -> tuple[int, int]:
        """Returns (sample_rate, channels) from audio file."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=sample_rate,channels",
                "-of", "json",
                str(file_path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            sample_rate = int(data["streams"][0]["sample_rate"])
            channels = int(data["streams"][0]["channels"])
            return sample_rate, channels
        except Exception:
            return 44100, 1

    @staticmethod
    def create_silence(duration: float, sample_rate: int, channels: int, output_path: Path) -> Path:
        """Generates silent audio segment of specified duration."""
        layout = "mono" if channels == 1 else "stereo"
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl={layout}",
            "-t", str(duration),
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def merge(
        chunk_files: List[Path],
        output_file: Path,
        pause_duration: float = 0.6,
        apply_loudnorm: bool = True,
        output_format: str = "wav",
        mp3_bitrate: str = "256k"
    ) -> Path:
        """
        Merges list of wav chunks with silence pauses between them,
        applies loudness normalization, and saves in target format.
        """
        if not chunk_files:
            raise ValueError("Список файлов для склейки пуст.")

        if len(chunk_files) == 1 and pause_duration == 0 and not apply_loudnorm and output_format == "wav":
            # Just copy if single file and no processing needed
            import shutil
            shutil.copy2(chunk_files[0], output_file)
            return output_file

        temp_dir = output_file.parent / ".tmp_merge"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        sample_rate, channels = AudioMerger.probe_audio(chunk_files[0])
        silent_file = None
        list_file_path = temp_dir / "concat_list.txt"

        try:
            if pause_duration > 0:
                silent_file = temp_dir / "silence.wav"
                AudioMerger.create_silence(pause_duration, sample_rate, channels, silent_file)

            with open(list_file_path, "w", encoding="utf-8") as f:
                for i, chunk_path in enumerate(chunk_files):
                    f.write(f"file '{chunk_path.resolve()}'\n")
                    if silent_file and i < len(chunk_files) - 1:
                        f.write(f"file '{silent_file.resolve()}'\n")

            # Build ffmpeg command
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file_path)
            ]

            if apply_loudnorm:
                cmd.extend(["-filter_complex", LOUDNORM_FILTER])

            fmt = output_format.lower()
            if fmt == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", mp3_bitrate])
            elif fmt in ["m4a", "m4b", "aac"]:
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            else:
                # Default PCM WAV 16-bit
                cmd.extend(["-c:a", "pcm_s16le"])

            output_file.parent.mkdir(parents=True, exist_ok=True)
            cmd.append(str(output_file))

            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg ошибка: {process.stderr}")

            return output_file

        finally:
            if list_file_path.exists():
                list_file_path.unlink()
            if silent_file and silent_file.exists():
                silent_file.unlink()
            if temp_dir.exists() and not any(temp_dir.iterdir()):
                temp_dir.rmdir()
