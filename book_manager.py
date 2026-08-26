import json
import re
import hashlib
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from config import BASE_DIR, OUTPUT_DIR

PROJECTS_DIR = BASE_DIR / "data" / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

class BookProjectManager:
    @staticmethod
    def normalize_str(s: str) -> str:
        if not s:
            return ""
        return unicodedata.normalize("NFC", s)

    @classmethod
    def get_book_id(cls, filename_or_title: str) -> str:
        """
        Generates a clean filesystem-safe slug/id for a book with NFC normalization.
        """
        norm = cls.normalize_str(filename_or_title)
        clean = re.sub(r"[^\w\sа-яА-ЯёЁa-zA-Z0-9-]", "", norm).strip()
        clean = re.sub(r"[\s-]+", "_", clean).lower()
        if not clean:
            clean = hashlib.md5(norm.encode("utf-8")).hexdigest()[:10]
        return clean

    @classmethod
    def get_project_file(cls, book_id: str) -> Path:
        return PROJECTS_DIR / f"{book_id}.json"

    @classmethod
    def load_project(cls, book_id: str) -> Optional[Dict[str, Any]]:
        file_path = cls.get_project_file(book_id)
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading project {book_id}: {e}")
        return None

    @classmethod
    def save_project(cls, book_id: str, data: Dict[str, Any]) -> None:
        file_path = cls.get_project_file(book_id)
        data["updated_at"] = datetime.now().isoformat()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving project {book_id}: {e}")

    @classmethod
    def sync_chapters_with_saved_progress(
        cls,
        book_title: str,
        chapters: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Merges new extracted chapters with previously saved progress log
        and scans the output/ directory for existing synthesized chapter audio files.
        """
        book_id = cls.get_book_id(book_title)
        saved_data = cls.load_project(book_id) or {}
        saved_chapters_map = {}
        
        if "chapters" in saved_data:
            for sc in saved_data["chapters"]:
                title_key = cls.normalize_str(sc.get("title", ""))
                if title_key:
                    saved_chapters_map[title_key] = sc
                norm_title = cls._normalize_title(title_key)
                if norm_title:
                    saved_chapters_map[norm_title] = sc
                if sc.get("id"):
                    saved_chapters_map[sc["id"]] = sc

        # Read actual audio files present in output/
        existing_output_files = [f for f in OUTPUT_DIR.glob("*.*") if f.suffix.lower() in [".mp3", ".wav", ".m4a", ".flac"]]

        for chap in chapters:
            raw_title = chap.get("title", "")
            chap_id = chap.get("id", "")
            norm_title = cls._normalize_title(raw_title)
            
            chap.setdefault("status", "idle")
            chap.setdefault("audio_url", None)
            chap.setdefault("completed_at", None)

            # 1. Match from project json log
            matched_record = (
                saved_chapters_map.get(chap_id) or 
                saved_chapters_map.get(raw_title) or 
                saved_chapters_map.get(norm_title)
            )
            
            if matched_record and matched_record.get("status") == "done":
                chap["status"] = "done"
                chap["audio_url"] = matched_record.get("audio_url")
                chap["completed_at"] = matched_record.get("completed_at")

            # 2. Check if physical audio file exists in output/ folder
            if norm_title:
                for out_file in existing_output_files:
                    out_norm = cls._normalize_title(out_file.stem)
                    if out_norm and (norm_title == out_norm or norm_title in out_norm or out_norm in norm_title):
                        if out_file.stat().st_size > 5000:
                            chap["status"] = "done"
                            chap["audio_url"] = f"/api/audio/output/{out_file.name}"
                            if not chap.get("completed_at"):
                                chap["completed_at"] = datetime.fromtimestamp(out_file.stat().st_mtime).isoformat()
                            break

        # Save synced state
        cls.save_project(book_id, {
            "book_id": book_id,
            "book_title": cls.normalize_str(book_title),
            "chapters": [
                {
                    "id": c.get("id"),
                    "index": c.get("index"),
                    "title": c.get("title"),
                    "char_count": c.get("char_count"),
                    "status": c.get("status", "idle"),
                    "audio_url": c.get("audio_url"),
                    "completed_at": c.get("completed_at")
                }
                for c in chapters
            ]
        })

        return book_id, chapters

    @classmethod
    def record_chapter_completion(
        cls,
        book_id: str,
        chapter_id: str,
        chapter_title: str,
        audio_url: str
    ) -> None:
        """
        Updates chapter status to 'done' and saves progress to project JSON.
        """
        norm_book_id = cls.get_book_id(book_id)
        data = cls.load_project(norm_book_id) or {
            "book_id": norm_book_id,
            "book_title": cls.normalize_str(chapter_title),
            "chapters": []
        }

        updated = False
        norm_target = cls._normalize_title(chapter_title)
        
        for c in data.get("chapters", []):
            if c.get("id") == chapter_id or (norm_target and cls._normalize_title(c.get("title", "")) == norm_target):
                c["status"] = "done"
                c["audio_url"] = audio_url
                c["completed_at"] = datetime.now().isoformat()
                updated = True
                break

        if not updated:
            data.setdefault("chapters", []).append({
                "id": chapter_id,
                "title": chapter_title,
                "status": "done",
                "audio_url": audio_url,
                "completed_at": datetime.now().isoformat()
            })

        cls.save_project(norm_book_id, data)

    @classmethod
    def get_all_projects(cls) -> List[Dict[str, Any]]:
        """
        Returns list of all saved book projects with their progress summary.
        """
        projects = []
        for p_file in PROJECTS_DIR.glob("*.json"):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    total_chaps = len(data.get("chapters", []))
                    done_chaps = sum(1 for c in data.get("chapters", []) if c.get("status") == "done")
                    projects.append({
                        "book_id": data.get("book_id", p_file.stem),
                        "book_title": data.get("book_title", p_file.stem),
                        "total_chapters": total_chaps,
                        "done_chapters": done_chaps,
                        "percent": round((done_chaps / total_chaps * 100) if total_chaps > 0 else 0),
                        "updated_at": data.get("updated_at")
                    })
            except Exception:
                pass
        return projects

    @classmethod
    def _normalize_title(cls, title: str) -> str:
        if not title:
            return ""
        t = cls.normalize_str(title)
        t = re.sub(r"^\d+[\.\s\-_:]+", "", t) # remove leading chapter numbers
        # Remove ALL underscores, punctuation, spaces, non-alphanumeric chars
        t = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9]", "", t).lower()
        return t
