import re
from pathlib import Path
import pypdf

class DocumentExtractor:
    @staticmethod
    def extract_from_pdf(pdf_path: str | Path) -> str:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF файл не найден: {pdf_path}")

        reader = pypdf.PdfReader(str(pdf_path))
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())

        full_text = "\n\n".join(pages_text)
        return DocumentExtractor.clean_text(full_text)

    @staticmethod
    def extract_from_txt(txt_path: str | Path) -> str:
        txt_path = Path(txt_path)
        if not txt_path.exists():
            raise FileNotFoundError(f"Текстовый файл не найден: {txt_path}")

        # Try utf-8 first, then cp1251/latin-1
        for encoding in ["utf-8", "utf-8-sig", "cp1251", "latin-1"]:
            try:
                with open(txt_path, "r", encoding=encoding) as f:
                    text = f.read()
                return DocumentExtractor.clean_text(text)
            except UnicodeDecodeError:
                continue

        raise ValueError(f"Не удалось декодировать файл: {txt_path}")

    @staticmethod
    def extract(file_path: str | Path) -> str:
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

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Replace soft hyphens ( переносы слов на концах строк )
        text = text.replace("\xad", "")
        
        # Merge hyphenated words at line breaks (e.g. "произве-\nдение" -> "произведение")
        text = re.sub(r"([а-яА-Яa-zA-Z0-9])-\n([а-яА-Яa-zA-Z0-9])", r"\1\2", text)
        
        # Replace multiple spaces with single space
        text = re.sub(r"[ \t]+", " ", text)
        
        # Collapse 3+ newlines into 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        return text.strip()
