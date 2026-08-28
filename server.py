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
from chapter_parser import ChapterParser
import json
from voice_manager import VoiceManager
from tts_client import FishAudioClient
from lumean_client import LumeanClient
from pipeline import TextToSpeechPipeline, PipelineProgress
from book_manager import BookProjectManager
from vedic_cleaner import VedicTextCleaner

app = FastAPI(title="AudioBook TTS Studio", description="Fish Audio S2 & Cloud TTS Book Narrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent settings
SETTINGS_FILE = DATA_DIR / "settings.json"

def get_app_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "tts_provider": "fish_audio",
        "lumean_api_key": "2ncy52mLjYy2uh7osawMqhIMIjopr7gMonXK1mG0JSylwy5oJW7VF1JcpyM0kI8Y",
        "lumean_bearer_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FwaS5sdW1lYW4uYXBwL2FwaS9yZWZyZXNoIiwiaWF0IjoxNzg3OTAyOTA1LCJleHAiOjE3ODc5MDY1MDUsIm5iZiI6MTc4NzkwMjkwNSwianRpIjoiZkF5alJQOGRzVnljZHpodiIsInN1YiI6IjgxNzYiLCJwcnYiOiIyM2JkNWM4OTQ5ZjYwMGFkYjM5ZTcwMWM0MDA4NzJkYjdhNTk3NmY3Iiwiand0cyI6IjAxYTA0NzUxLTRkZGItNzFhOC1iY2RhLTE5MjIxYjAzNDA1MyJ9.0f4FzvkZpIs-Foj0EQSAYs20VBIBLT58fSVia8da9JE",
        "lumean_voice_id": ""
    }

def save_app_settings(data: Dict[str, Any]):
    current = get_app_settings()
    current.update(data)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

# Services
dictionary = StressDictionary()
voice_mgr = VoiceManager()
tts_client = FishAudioClient()
_settings = get_app_settings()
lumean_client = LumeanClient(
    api_key=_settings.get("lumean_api_key", ""),
    bearer_token=_settings.get("lumean_bearer_token", "")
)
pipeline = TextToSpeechPipeline(
    dictionary=dictionary,
    voice_manager=voice_mgr,
    tts_client=tts_client,
    lumean_client=lumean_client
)

# In-memory session tracking
sessions: Dict[str, PipelineProgress] = {}

# --- Schemas ---
class DictionaryEntry(BaseModel):
    word: str
    replacement: str

class PreviewRequest(BaseModel):
    text: str
    max_chunk_len: int = DEFAULT_CHUNK_LENGTH

class VedicCleanRequest(BaseModel):
    text: str

class AppSettingsRequest(BaseModel):
    tts_provider: Optional[str] = "fish_audio"
    lumean_api_key: Optional[str] = None
    lumean_bearer_token: Optional[str] = None
    lumean_refresh_token: Optional[str] = None
    lumean_voice_id: Optional[str] = None

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
    book_id: Optional[str] = None
    chapter_id: Optional[str] = None
    chapter_title: Optional[str] = None
    provider: Optional[str] = "fish_audio"
    lumean_voice_id: Optional[str] = None
    lumean_api_key: Optional[str] = None
    lumean_bearer_token: Optional[str] = None

class RecordChapterRequest(BaseModel):
    book_id: str
    chapter_id: str
    chapter_title: str
    audio_url: str

class VoiceSettingsRequest(BaseModel):
    speed: float = 1.0
    pause_duration: float = DEFAULT_PAUSE_DURATION
    temperature: float = 0.88
    instruct: Optional[str] = None


# --- API Routes ---

@app.get("/api/settings")
def get_settings():
    return get_app_settings()

@app.post("/api/settings")
def update_settings(req: AppSettingsRequest):
    data = req.dict(exclude_none=True)
    save_app_settings(data)
    if "lumean_api_key" in data:
        lumean_client.api_key = data["lumean_api_key"]
    return {"status": "ok", "settings": get_app_settings()}

@app.get("/api/lumean/test")
def test_lumean():
    settings = get_app_settings()
    client = LumeanClient(api_key=settings.get("lumean_api_key", ""))
    return client.check_connection()

@app.get("/api/lumean/voices")
def get_lumean_voices():
    settings = get_app_settings()
    client = LumeanClient(api_key=settings.get("lumean_api_key", ""))
    return client.fetch_voices()

@app.post("/api/lumean/sync_browser")
def sync_lumean_tokens_from_browser():
    """
    Automatically extracts current token and refresh_token from open lumean.app tab in Google Chrome.
    """
    script = '''
    tell application "Google Chrome"
        repeat with w in windows
            repeat with t in tabs of w
                if URL of t contains "lumean.app" then
                    set res to execute t javascript "JSON.stringify({token: localStorage.getItem('token') || localStorage.getItem('access_token'), refresh_token: localStorage.getItem('refresh_token')})"
                    return res
                end if
            end repeat
        end repeat
        return "not_found"
    end tell
    '''
    try:
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
        if proc.returncode != 0:
            err = proc.stderr
            if "AppleScript" in err or "JavaScript" in err or "12" in err:
                return {
                    "success": False,
                    "need_permission": True,
                    "message": "Включите в Google Chrome (1 раз): верхнее меню «Вид» ➔ «Разработчикам» ➔ «Разрешить JavaScript из событий Apple»."
                }
            return {"success": False, "message": f"Ошибка Chrome: {err[:150]}"}
        
        output = proc.stdout.strip()
        if output == "not_found":
            return {
                "success": False,
                "message": "В Google Chrome не найдена открытая вкладка lumean.app. Откройте сайт lumean.app в браузере и нажмите кнопку снова."
            }
        
        data = json.loads(output)
        token = data.get("token")
        refresh_token = data.get("refresh_token")
        
        if not token or not refresh_token:
            return {
                "success": False,
                "message": "Токены не найдены на странице lumean.app. Убедитесь, что вы авторизованы в аккаунте на сайте."
            }
        
        # Save to settings
        settings = get_app_settings()
        settings["lumean_bearer_token"] = token
        settings["lumean_access_token"] = token
        settings["lumean_refresh_token"] = refresh_token
        settings["tts_provider"] = "lumean"
        save_app_settings(settings)
        lumean_client.bearer_token = token
        
        return {
            "success": True,
            "message": "✅ Токены успешно и автоматически скопированы из Google Chrome!",
            "bearer_token": token,
            "refresh_token": refresh_token
        }
    except Exception as e:
        return {"success": False, "message": f"Ошибка синхронизации: {str(e)}"}

@app.get("/api/status")
def get_status():
    tts_online = tts_client.check_connection()
    lumean_status = lumean_client.check_connection()
    return {
        "status": "online",
        "fish_audio_url": tts_client.api_url,
        "fish_audio_connected": tts_online,
        "lumean_status": lumean_status,
        "default_voice_exists": Path("/Users/jeka/fish-audio-s2/voice/reference.wav").exists(),
        "settings": get_app_settings()
    }

@app.post("/api/vedic/clean")
def clean_vedic_text(req: VedicCleanRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Текст для очистки пуст")
    return VedicTextCleaner.clean_with_stats(req.text)

@app.post("/api/vedic/clean-file")
async def clean_vedic_file(file: UploadFile = File(...)):
    filename = file.filename or "book.txt"
    temp_path = CACHE_DIR / f"clean_upload_{filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        extracted = DocumentExtractor.extract(temp_path)
        raw_text = extracted["raw_text"]
        result = VedicTextCleaner.clean_with_stats(raw_text)
        result["filename"] = filename
        return result
    finally:
        if temp_path.exists():
            temp_path.unlink()

@app.get("/api/voices")
def get_voices():
    voices = voice_mgr.list_voices()
    return [v.to_dict() for v in voices]

@app.post("/api/voices/{name}/settings")
def update_voice_settings(name: str, req: VoiceSettingsRequest):
    try:
        updated = voice_mgr.update_voice_settings(
            name=name,
            speed=req.speed,
            pause_duration=req.pause_duration,
            temperature=req.temperature,
            instruct=req.instruct
        )
        return {"status": "saved", "voice": updated.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
    filename = file.filename or "Книга"
    temp_path = CACHE_DIR / f"upload_{filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        extracted = DocumentExtractor.extract(temp_path)
        raw_text = extracted["raw_text"]
        chapters_raw = extracted["chapters_raw"]
        
        base_title = Path(filename).stem
        book_id, synced_chapters = BookProjectManager.sync_chapters_with_saved_progress(base_title, chapters_raw)
        
        # Enrich chapters with stressed text and chunks
        processed_chapters = []
        all_chunks = []
        for idx, chap in enumerate(synced_chapters):
            stressed = dictionary.apply(chap["text"])
            chap_chunks = TextChunker.split_into_chunks(stressed)
            all_chunks.extend(chap_chunks)
            processed_chapters.append({
                "id": chap.get("id") or f"chapter_{idx + 1}",
                "index": idx + 1,
                "title": chap["title"],
                "text": chap["text"],
                "stressed_text": stressed,
                "chunks": chap_chunks,
                "char_count": len(chap["text"]),
                "chunk_count": len(chap_chunks),
                "status": chap.get("status", "idle"),
                "audio_url": chap.get("audio_url"),
                "completed_at": chap.get("completed_at")
            })

        return {
            "filename": filename,
            "book_id": book_id,
            "raw_text": raw_text,
            "chapters": processed_chapters,
            "total_chars": len(raw_text),
            "total_chapters": len(processed_chapters),
            "total_chunks": len(all_chunks),
            "done_chapters": sum(1 for c in processed_chapters if c.get("status") == "done")
        }
    finally:
        if temp_path.exists():
            temp_path.unlink()

@app.post("/api/preview")
def preview_text(req: PreviewRequest):
    raw_text = DocumentExtractor.clean_text(req.text)
    chapters_raw = ChapterParser.split_into_chapters(raw_text, default_book_title="Книга")
    book_id, synced_chapters = BookProjectManager.sync_chapters_with_saved_progress("Книга", chapters_raw)
    
    processed_chapters = []
    all_chunks = []
    for idx, chap in enumerate(synced_chapters):
        stressed = dictionary.apply(chap["text"])
        chap_chunks = TextChunker.split_into_chunks(stressed, max_chunk_len=req.max_chunk_len)
        all_chunks.extend(chap_chunks)
        processed_chapters.append({
            "id": chap.get("id") or f"chapter_{idx + 1}",
            "index": idx + 1,
            "title": chap["title"],
            "text": chap["text"],
            "stressed_text": stressed,
            "chunks": chap_chunks,
            "char_count": len(chap["text"]),
            "chunk_count": len(chap_chunks),
            "status": chap.get("status", "idle"),
            "audio_url": chap.get("audio_url"),
            "completed_at": chap.get("completed_at")
        })

    return {
        "book_id": book_id,
        "raw_text": raw_text,
        "chapters": processed_chapters,
        "total_chars": len(raw_text),
        "total_chapters": len(processed_chapters),
        "total_chunks": len(all_chunks),
        "done_chapters": sum(1 for c in processed_chapters if c.get("status") == "done")
    }

@app.get("/api/projects")
def list_book_projects():
    return BookProjectManager.get_all_projects()

@app.get("/api/projects/{book_id}")
def get_book_project(book_id: str):
    data = BookProjectManager.load_project(book_id)
    if not data:
        raise HTTPException(status_code=404, detail="Проект книги не найден")
    return data

@app.post("/api/projects/record-chapter")
def record_chapter(req: RecordChapterRequest):
    BookProjectManager.record_chapter_completion(
        book_id=req.book_id,
        chapter_id=req.chapter_id,
        chapter_title=req.chapter_title,
        audio_url=req.audio_url
    )
    return {"status": "saved", "book_id": req.book_id, "chapter_id": req.chapter_id}

def run_pipeline_task(session_id: str, req: GenerateRequest):
    prog = sessions[session_id]
    
    def on_progress(p: PipelineProgress):
        sessions[session_id] = p

    try:
        app_settings = get_app_settings()
        custom_params = {
            "speed": req.speed,
            "temperature": req.temperature,
            "top_p": req.top_p,
            "top_k": req.top_k,
            "chunk_length": req.chunk_length,
            "provider": req.provider or app_settings.get("tts_provider", "fish_audio"),
            "lumean_voice_id": req.lumean_voice_id or app_settings.get("lumean_voice_id", ""),
            "lumean_api_key": req.lumean_api_key or app_settings.get("lumean_api_key", "")
        }
        if req.instruct:
            custom_params["instruct"] = req.instruct

        chunks_to_process = req.chunks if (req.chunks and len(req.chunks) > 0) else req.text

        res_prog = pipeline.process(
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

        # Auto-record chapter completion in book manager log
        completed_prog = res_prog if (res_prog and res_prog.status == "completed") else sessions.get(session_id)
        if completed_prog and completed_prog.status == "completed" and completed_prog.output_file and req.book_id:
            audio_url = f"/api/audio/output/{completed_prog.output_file.name}"
            chap_id = req.chapter_id or f"chap_{session_id}"
            chap_title = req.output_name or req.chapter_title or "Chapter"
            BookProjectManager.record_chapter_completion(req.book_id, chap_id, chap_title, audio_url)

    except Exception as e:
        if prog.status != "cancelled":
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

@app.post("/api/cancel/{session_id}")
def cancel_generation(session_id: str):
    if session_id in sessions:
        prog = sessions[session_id]
        prog.status = "cancelled"
        prog.message = "Озвучка отменена пользователем."
    pipeline.cancel(session_id)
    print(f"🛑 [Server] Отмена задачи {session_id}")
    return {"status": "cancelled", "session_id": session_id}

@app.post("/api/cancel-all")
def cancel_all_generations():
    for sid, prog in sessions.items():
        if prog.status in ["queued", "processing", "merging"]:
            prog.status = "cancelled"
            prog.message = "Озвучка отменена пользователем."
            pipeline.cancel(sid)
    print("🛑 [Server] Все активные задачи генерации принудительно остановлены.")
    return {"status": "all_cancelled"}

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
