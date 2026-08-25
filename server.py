import os
import shutil
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    BASE_DIR, DATA_DIR, OUTPUT_DIR, CACHE_DIR, VOICES_DIR,
    DEFAULT_TTS_URL, DEFAULT_CHUNK_LENGTH, DEFAULT_PAUSE_DURATION,
    DEFAULT_AUDIO_FORMAT, DEFAULT_GENERATION_PARAMS
)
from extractor import DocumentExtractor
from stress_dict import StressDictionary
from chunker import TextChunker
from voice_manager import VoiceManager
from tts_client import FishAudioClient
from pipeline import TextToSpeechPipeline, PipelineProgress

app = FastAPI(title="AudioBook TTS Studio", description="Fish Audio S2 Book Narrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
dictionary = StressDictionary()
voice_mgr = VoiceManager()
tts_client = FishAudioClient()
pipeline = TextToSpeechPipeline(dictionary, voice_mgr, tts_client)

# In-memory session tracking
sessions: Dict[str, PipelineProgress] = {}

# --- Schemas ---
class DictionaryEntry(BaseModel):
    word: str
    replacement: str

class PreviewRequest(BaseModel):
    text: str
    max_chunk_len: int = DEFAULT_CHUNK_LENGTH

class GenerateRequest(BaseModel):
    chunks: Optional[List[str]] = None
    text: Optional[str] = None
    voice_name: str = "default"
    output_name: Optional[str] = None
    output_format: str = "wav"
    max_chunk_len: int = DEFAULT_CHUNK_LENGTH
    pause_duration: float = DEFAULT_PAUSE_DURATION
    apply_loudnorm: bool = True
    speed: float = 1.0
    temperature: float = 0.85
    top_p: float = 0.85
    top_k: int = 30
    chunk_length: int = 300
    instruct: Optional[str] = None


# --- API Routes ---

@app.get("/api/status")
def get_status():
    tts_online = tts_client.check_connection()
    return {
        "status": "online",
        "fish_audio_url": tts_client.api_url,
        "fish_audio_connected": tts_online,
        "default_voice_exists": Path("/Users/jeka/fish-audio-s2/voice/reference.wav").exists()
    }

@app.get("/api/voices")
def get_voices():
    voices = voice_mgr.list_voices()
    return [v.to_dict() for v in voices]

@app.post("/api/voices")
async def create_voice(name: str = Form(...), text: str = Form(...), audio: UploadFile = File(...)):
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Имя голоса не может быть пустым")
    
    temp_path = CACHE_DIR / f"upload_{audio.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    try:
        profile = voice_mgr.add_voice(name, temp_path, text)
        return profile.to_dict()
    finally:
        if temp_path.exists():
            temp_path.unlink()

@app.delete("/api/voices/{name}")
def delete_voice(name: str):
    if name == "default":
        raise HTTPException(status_code=400, detail="Нельзя удалить голос по умолчанию")
    success = voice_mgr.delete_voice(name)
    if not success:
        raise HTTPException(status_code=404, detail="Голос не найден")
    return {"status": "deleted", "name": name}

@app.get("/api/dictionary")
def get_dictionary():
    return dictionary.entries

@app.post("/api/dictionary")
def update_dictionary_entry(entry: DictionaryEntry):
    dictionary.add_entry(entry.word, entry.replacement)
    return {"status": "saved", "word": entry.word, "replacement": entry.replacement}

@app.delete("/api/dictionary/{word}")
def delete_dictionary_entry(word: str):
    success = dictionary.remove_entry(word)
    if not success:
        raise HTTPException(status_code=404, detail="Слово не найдено в словаре")
    return {"status": "deleted", "word": word}

@app.post("/api/extract")
async def extract_file_text(file: UploadFile = File(...)):
    filename = file.filename or "temp_file"
    temp_path = CACHE_DIR / f"upload_{filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        raw_text = DocumentExtractor.extract(temp_path)
        stressed_text = dictionary.apply(raw_text)
        chunks = TextChunker.split_into_chunks(stressed_text)
        return {
            "filename": filename,
            "raw_text": raw_text,
            "stressed_text": stressed_text,
            "chunks": chunks,
            "total_chars": len(raw_text),
            "chunk_count": len(chunks)
        }
    finally:
        if temp_path.exists():
            temp_path.unlink()

@app.post("/api/preview")
def preview_text(req: PreviewRequest):
    raw_text = DocumentExtractor.clean_text(req.text)
    stressed_text = dictionary.apply(raw_text)
    chunks = TextChunker.split_into_chunks(stressed_text, max_chunk_len=req.max_chunk_len)
    return {
        "raw_text": raw_text,
        "stressed_text": stressed_text,
        "chunks": chunks,
        "total_chars": len(raw_text),
        "chunk_count": len(chunks)
    }

def run_pipeline_task(session_id: str, req: GenerateRequest):
    prog = sessions[session_id]
    
    def on_progress(p: PipelineProgress):
        sessions[session_id] = p

    try:
        custom_params = {
            "speed": req.speed,
            "temperature": req.temperature,
            "top_p": req.top_p,
            "top_k": req.top_k,
            "chunk_length": req.chunk_length
        }
        if req.instruct:
            custom_params["instruct"] = req.instruct

        chunks_to_process = req.chunks if (req.chunks and len(req.chunks) > 0) else req.text

        pipeline.process(
            text_or_chunks=chunks_to_process,
            voice_name=req.voice_name,
            output_name=req.output_name,
            output_format=req.output_format,
            max_chunk_len=req.max_chunk_len,
            pause_duration=req.pause_duration,
            apply_loudnorm=req.apply_loudnorm,
            custom_tts_params=custom_params,
            progress_callback=on_progress,
            session_id=session_id
        )
    except Exception as e:
        prog.status = "error"
        prog.error = str(e)
        prog.message = f"Ошибка генерации: {e}"

@app.post("/api/generate")
def start_generation(req: GenerateRequest, background_tasks: BackgroundTasks):
    if not req.chunks and not req.text:
        raise HTTPException(status_code=400, detail="Не передан текст или чанки для озвучки")

    chunk_list = req.chunks if req.chunks else TextChunker.split_into_chunks(dictionary.apply(req.text or ""))
    prog = PipelineProgress(total_chunks=len(chunk_list))
    prog.status = "queued"
    prog.message = "Запуск конвейера озвучки..."
    sessions[prog.session_id] = prog

    background_tasks.add_task(run_pipeline_task, prog.session_id, req)
    return {"session_id": prog.session_id, "total_chunks": len(chunk_list)}

@app.get("/api/progress/{session_id}")
def get_progress(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    prog = sessions[session_id]
    
    # Map audio paths to web URLs
    chunk_list = []
    for c in prog.chunk_statuses:
        c_dict = c.copy()
        if c_dict.get("audio_path"):
            rel_path = Path(c_dict["audio_path"]).name
            c_dict["audio_url"] = f"/api/audio/cache/{prog.session_id}/{rel_path}"
        chunk_list.append(c_dict)

    output_url = None
    if prog.output_file and prog.output_file.exists():
        output_url = f"/api/audio/output/{prog.output_file.name}"

    return {
        "session_id": prog.session_id,
        "status": prog.status,
        "total_chunks": prog.total_chunks,
        "current_chunk": prog.current_chunk,
        "message": prog.message,
        "error": prog.error,
        "chunks": chunk_list,
        "output_url": output_url
    }

@app.get("/api/audio/cache/{session_id}/{filename}")
def serve_chunk_audio(session_id: str, filename: str):
    file_path = CACHE_DIR / session_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Аудио чанк не найден")
    return FileResponse(file_path, media_type="audio/wav")

@app.post("/api/open-output-folder")
def open_output_folder():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    p = str(OUTPUT_DIR.resolve())
    import subprocess, sys

    if sys.platform == "darwin":
        files = list(OUTPUT_DIR.glob("*.mp3")) + list(OUTPUT_DIR.glob("*.wav"))
        if files:
            subprocess.run(["open", "-R", str(files[0].resolve())], check=False)
        else:
            subprocess.run(["open", p], check=False)
    elif sys.platform == "win32":
        try:
            os.startfile(p)
        except Exception:
            pass
    else:
        try:
            subprocess.run(["xdg-open", p], check=False)
        except Exception:
            pass

    return {"status": "opened", "path": p}

@app.get("/api/outputs")
def get_output_files():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(OUTPUT_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in [".mp3", ".wav", ".m4b", ".m4a"]:
            size_mb = round(f.stat().st_size / (1024 * 1024), 2)
            time_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(f.stat().st_mtime))
            files.append({
                "name": f.name,
                "size_mb": size_mb,
                "date": time_str,
                "url": f"/api/audio/output/{f.name}"
            })
    return {"files": files, "folder_path": str(OUTPUT_DIR.resolve())}

@app.get("/api/audio/output/{filename}")
def serve_output_audio(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Итоговый файл не найден")
    media = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
    return FileResponse(file_path, media_type=media, filename=filename)

@app.get("/api/audio/voice/{filename}")
def serve_voice_audio(filename: str):
    file_path = VOICES_DIR / filename
    if not file_path.exists():
        # Fallback to system reference
        if filename == "reference.wav" and Path("/Users/jeka/fish-audio-s2/voice/reference.wav").exists():
            return FileResponse(Path("/Users/jeka/fish-audio-s2/voice/reference.wav"), media_type="audio/wav")
        raise HTTPException(status_code=404, detail="Референс не найден")
    return FileResponse(file_path, media_type="audio/wav")

# Serve Frontend static assets
static_dir = BASE_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
