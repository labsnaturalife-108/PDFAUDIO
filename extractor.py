import re
from pathlib import Path
from typing import Dict, Any, List
import pypdf
from chapter_parser import ChapterParser

class DocumentExtractor:
    @staticmethod
    def extract_from_pdf(pdf_path: str | Path) -> Dict[str, Any]:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF файл не найден: {pdf_path}")

        reader = pypdf.PdfReader(str(pdf_path))
        num_pages = len(reader.pages)

        # 1. Strategy A: Extract via PDF Outline Bookmarks
        outline_chapters = []
        try:
            def parse_outline(outline):
                items = []
                for it in outline:
                    if isinstance(it, list):
                        items.extend(parse_outline(it))
                    elif hasattr(it, 'title'):
                        try:
                            page_num = reader.get_destination_page_number(it)
                            items.append((page_num, it.title.strip()))
                        except Exception:
                            pass
                return items

            if reader.outline:
                outline_items = parse_outline(reader.outline)
                outline_items.sort(key=lambda x: x[0])
                
                if len(outline_items) > 1:
                    for idx, (p_num, title) in enumerate(outline_items):
                        next_p = outline_items[idx + 1][0] if idx + 1 < len(outline_items) else num_pages
                        chap_pages = []
                        for p in range(p_num, next_p):
                            txt = reader.pages[p].extract_text() or ''
                            txt = re.sub(r'\n\d+\s*$', '', txt).strip()
                            if txt:
                                chap_pages.append(txt)
                        
                        chap_text = DocumentExtractor.clean_text("\n\n".join(chap_pages))
                        if chap_text:
                            outline_chapters.append({
                                "title": title,
                                "text": chap_text,
                                "char_count": len(chap_text)
                            })
        except Exception:
            outline_chapters = []

        # If outline bookmarks produced chapters, return them directly
        if len(outline_chapters) > 1:
            all_text = "\n\n".join([f"## {c['title']}\n\n{c['text']}" for c in outline_chapters])
            return {
                "raw_text": all_text,
                "chapters_raw": outline_chapters
            }

        # 2. Strategy B: Page-by-Page Title Extraction
        page_texts = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ''
            txt_clean = re.sub(r'\n\d+\s*$', '', txt).strip()
            if txt_clean:
                page_texts.append((i + 1, txt_clean))

        full_text_pages = "\n\n".join([p[1] for p in page_texts])
        full_cleaned = DocumentExtractor.clean_text(full_text_pages)

        # Use multi-pattern chapter parser
        base_title = pdf_path.stem
        chapters = ChapterParser.split_into_chapters(full_cleaned, default_book_title=base_title)
        
        return {
            "raw_text": full_cleaned,
            "chapters_raw": chapters
        }

    @staticmethod
    def extract_from_txt(txt_path: str | Path) -> Dict[str, Any]:
        txt_path = Path(txt_path)
        if not txt_path.exists():
            raise FileNotFoundError(f"Текстовый файл не найден: {txt_path}")

        raw_content = ""
        for encoding in ["utf-8", "utf-8-sig", "cp1251", "latin-1"]:
            try:
                with open(txt_path, "r", encoding=encoding) as f:
                    raw_content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if not raw_content:
            raise ValueError(f"Не удалось декодировать файл: {txt_path}")

        cleaned = DocumentExtractor.clean_text(raw_content)
        base_title = txt_path.stem
        chapters = ChapterParser.split_into_chapters(cleaned, default_book_title=base_title)

        return {
            "raw_text": cleaned,
            "chapters_raw": chapters
        }

    @staticmethod
    def extract(file_path: str | Path) -> Dict[str, Any]:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return DocumentExtractor.extract_from_pdf(path)
        elif suffix in [".txt", ".md", ".text"]:
            return DocumentExtractor.extract_from_txt(path)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {suffix}. Поддерживаются: .pdf, .txt, .md")

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\xad", "")
        text = re.sub(r"([а-яА-Яa-zA-Z0-9])-\n([а-яА-Яa-zA-Z0-9])", r"\1\2", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
