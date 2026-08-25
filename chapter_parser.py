import re
from typing import List, Dict, Any

class ChapterParser:
    # Patterns that typically mark the beginning of a new chapter
    CHAPTER_PATTERNS = [
        # Markdown headers (# Header, ## Header, ### Header)
        r"(?:^|\n)(?=(?:#{1,3}\s+[^\n]+))",
        
        # Russian / English Chapter titles (e.g. "Глава 1", "ГЛАВА I", "Глава первая", "Chapter 1")
        r"(?:^|\n)(?=(?:(?:ГЛАВА|Глава|глава|CHAPTER|Chapter|chapter)\s+(?:[0-9]+|[IVXLCDMivxlcdm]+|[А-Яа-яA-Za-z]+)(?:[.:\s—–-][^\n]*)?))",
        
        # Parts (e.g. "Часть 1", "Часть I", "Part 1")
        r"(?:^|\n)(?=(?:(?:ЧАСТЬ|Часть|часть|PART|Part|part)\s+(?:[0-9]+|[IVXLCDMivxlcdm]+|[А-Яа-яA-Za-z]+)(?:[.:\s—–-][^\n]*)?))",
        
        # Sanskrit / Verse texts (e.g. "Текст 1", "Текст 1.1", "ТЕКСТ 1")
        r"(?:^|\n)(?=(?:(?:ТЕКСТ|Текст|текст|СТИХ|Стих|стих|TEXT|Text)\s+[0-9]+(?:\.[0-9]+)?(?:[.:\s—–-][^\n]*)?))",
        
        # Standard special sections (Пролог, Эпилог, Введение, Предисловие, Заключение)
        r"(?:^|\n)(?=(?:(?:ПРОЛОГ|Пролог|ЭПИЛОГ|Эпилог|ВВЕДЕНИЕ|Введение|ПРЕДИСЛОВИЕ|Предисловие|ЗАКЛЮЧЕНИЕ|Заключение|ПОСЛЕСЛОВИЕ|Послесловие)(?:[.:\s—–-][^\n]*)?))",
        
        # Roman numerals as chapter headers on separate lines (e.g. "\n\nI.\n", "\n\nII. Название\n")
        r"(?:^|\n)(?=(?:[IVXLCDM]+\.\s+[^\n]+))"
    ]

    @staticmethod
    def split_into_chapters(full_text: str, default_book_title: str = "Книга") -> List[Dict[str, Any]]:
        """
        Splits book text into chapters. If chapters are detected, returns list of chapters.
        If no chapter markers are found, returns the entire text as Chapter 1 (or splits by fixed size if very long).
        """
        if not full_text or not full_text.strip():
            return []

        text = full_text.strip()

        # Combine all patterns into one master regex
        master_pattern = "|".join(ChapterParser.CHAPTER_PATTERNS)
        
        # Split text while keeping boundaries
        raw_parts = re.split(master_pattern, text)
        raw_parts = [p.strip() for p in raw_parts if p and p.strip()]

        chapters = []

        # If splitting resulted in multiple meaningful parts (>1)
        if len(raw_parts) > 1:
            for idx, part in enumerate(raw_parts):
                lines = part.split("\n")
                first_line = lines[0].strip().lstrip("#").strip()
                
                # Check if first line looks like a title
                if len(first_line) <= 120:
                    title = first_line
                    body = "\n".join(lines[1:]).strip()
                    if not body:
                        # If the whole part was just one line, keep it
                        body = part
                else:
                    title = f"Глава {idx + 1}"
                    body = part

                if body:
                    chapters.append({
                        "id": f"chapter_{idx + 1}",
                        "index": idx + 1,
                        "title": title or f"Глава {idx + 1}",
                        "text": body,
                        "char_count": len(body),
                        "status": "idle",
                        "audio_url": None
                    })
        else:
            # If no chapters detected automatically, check if text is very large (> 25000 chars)
            # If so, split into natural ~15000 char sections without breaking paragraphs
            if len(text) > 25000:
                paragraphs = text.split("\n\n")
                current_chap_text = []
                current_len = 0
                part_num = 1

                for para in paragraphs:
                    current_chap_text.append(para)
                    current_len += len(para) + 2
                    if current_len >= 15000:
                        body_content = "\n\n".join(current_chap_text).strip()
                        chapters.append({
                            "id": f"chapter_{part_num}",
                            "index": part_num,
                            "title": f"Часть {part_num}",
                            "text": body_content,
                            "char_count": len(body_content),
                            "status": "idle",
                            "audio_url": None
                        })
                        current_chap_text = []
                        current_len = 0
                        part_num += 1

                if current_chap_text:
                    body_content = "\n\n".join(current_chap_text).strip()
                    chapters.append({
                        "id": f"chapter_{part_num}",
                        "index": part_num,
                        "title": f"Часть {part_num}",
                        "text": body_content,
                        "char_count": len(body_content),
                        "status": "idle",
                        "audio_url": None
                    })
            else:
                # Single chapter
                chapters.append({
                    "id": "chapter_1",
                    "index": 1,
                    "title": default_book_title or "Глава 1",
                    "text": text,
                    "char_count": len(text),
                    "status": "idle",
                    "audio_url": None
                })

        return chapters
