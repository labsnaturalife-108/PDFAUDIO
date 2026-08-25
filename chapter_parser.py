import re
from typing import List, Dict, Any

class ChapterParser:
    @staticmethod
    def is_chapter_header_line(line: str) -> bool:
        """
        Determines if a single line looks like a chapter header.
        """
        line = line.strip()
        if not line or len(line) < 2 or len(line) > 110:
            return False

        # 1. Markdown headers (# Header, ## Header, ### Header)
        if re.match(r"^#{1,3}\s+[^\n]+$", line):
            return True

        # 2. Standard explicit Russian / English Chapter keywords
        keyword_pattern = (
            r"^(?:(?:ГЛАВА|Глава|глава|CHAPTER|Chapter|chapter)\s+(?:[0-9]+|[IVXLCDMivxlcdm]+|[А-Яа-яA-Za-z]+)|"
            r"(?:ЧАСТЬ|Часть|часть|PART|Part|part)\s+(?:[0-9]+|[IVXLCDMivxlcdm]+|[А-Яа-яA-Za-z]+)|"
            r"(?:ТЕКСТ|Текст|текст|СТИХ|Стих|стих|TEXT|Text)\s+[0-9]+(?:\.[0-9]+)?|"
            r"(?:ПРОЛОГ|Пролог|ЭПИЛОГ|Эпилог|ВВЕДЕНИЕ|Введение|ПРЕДИСЛОВИЕ|Предисловие|ЗАКЛЮЧЕНИЕ|Заключение|ПОСЛЕСЛОВИЕ|Послесловие))"
            r"(?:[.:\s—–-].*)?$"
        )
        if re.match(keyword_pattern, line, flags=re.IGNORECASE):
            return True

        # 3. Numbered titles like "1. Название", "2. Название", "I. Название", "II. Название"
        if re.match(r"^(?:[0-9]{1,3}|[IVXLCDM]{1,8})\.\s+[А-ЯЁA-Zа-яёa-z].*$", line):
            return True

        # 4. ALL-CAPS titles (e.g. "ДРУГАЯ СТОРОНА", "ПОЛЕТ В БЕЗДНУ", "ТАЙНА ТЕМНОГО ЛЕСА")
        # Line must contain at least one letter, and all letters must be UPPERCASE.
        # Should not end with a period or question mark (which indicates regular sentence).
        letters = [c for c in line if c.isalpha()]
        if len(letters) >= 3 and all(c.isupper() for c in letters):
            # Exclude lines that look like standard sentences with terminal punctuation
            if not line.endswith((".", "?", "!", ";", ",")):
                return True

        # 5. Section dividers (e.g. "***", "* * *", "---")
        if re.match(r"^(?:\*{3,}|\*\s+\*\s+\*|-{3,}|_{3,})$", line):
            return True

        return False

    @staticmethod
    def split_into_chapters(full_text: str, default_book_title: str = "Книга") -> List[Dict[str, Any]]:
        """
        Splits text into chapters using multiple strategies:
        1. Explicit keywords and ALL-CAPS headers.
        2. If no headers found and text is long (>15 000 chars), splits by paragraph blocks into ~10k-15k parts.
        """
        if not full_text or not full_text.strip():
            return []

        text = full_text.strip()
        lines = text.split("\n")

        raw_chapters = []
        current_title = ""
        current_body_lines = []

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                if current_body_lines:
                    current_body_lines.append("")
                continue

            if ChapterParser.is_chapter_header_line(trimmed):
                # If we already have accumulated body text, save previous chapter
                if current_body_lines:
                    body_text = "\n".join(current_body_lines).strip()
                    if body_text:
                        raw_chapters.append({
                            "title": current_title or default_book_title or f"Глава {len(raw_chapters) + 1}",
                            "text": body_text
                        })
                    current_body_lines = []

                # Clean markdown hashtags from title
                clean_title = re.sub(r"^#{1,3}\s+", "", trimmed).strip()
                # If it was just a divider like "***", name it Part N
                if re.match(r"^(?:\*{3,}|\*\s+\*\s+\*|-{3,}|_{3,})$", clean_title):
                    clean_title = f"Часть {len(raw_chapters) + 1}"

                current_title = clean_title
            else:
                current_body_lines.append(trimmed)

        # Append final chapter
        if current_body_lines:
            body_text = "\n".join(current_body_lines).strip()
            if body_text:
                raw_chapters.append({
                    "title": current_title or (f"Глава {len(raw_chapters) + 1}" if raw_chapters else default_book_title),
                    "text": body_text
                })

        # --- Post-Processing / Fallbacks ---

        # If splitting produced only 1 huge chapter (> 15 000 chars)
        if len(raw_chapters) <= 1:
            main_text = raw_chapters[0]["text"] if raw_chapters else text
            main_title = raw_chapters[0]["title"] if raw_chapters else default_book_title

            if len(main_text) > 15000:
                paragraphs = main_text.split("\n\n")
                current_chunk_paras = []
                current_len = 0
                part_idx = 1
                fallback_chapters = []

                for p in paragraphs:
                    current_chunk_paras.append(p)
                    current_len += len(p) + 2
                    # Natural chapter boundary ~12 000 characters
                    if current_len >= 12000:
                        part_body = "\n\n".join(current_chunk_paras).strip()
                        fallback_chapters.append({
                            "title": f"{main_title} — Часть {part_idx}",
                            "text": part_body
                        })
                        current_chunk_paras = []
                        current_len = 0
                        part_idx += 1

                if current_chunk_paras:
                    part_body = "\n\n".join(current_chunk_paras).strip()
                    fallback_chapters.append({
                        "title": f"{main_title} — Часть {part_idx}",
                        "text": part_body
                    })

                raw_chapters = fallback_chapters

        # Format output structures with IDs and character counts
        formatted_chapters = []
        for idx, chap in enumerate(raw_chapters):
            formatted_chapters.append({
                "id": f"chapter_{idx + 1}",
                "index": idx + 1,
                "title": chap["title"] or f"Глава {idx + 1}",
                "text": chap["text"],
                "char_count": len(chap["text"]),
                "status": "idle",
                "audio_url": None
            })

        return formatted_chapters
