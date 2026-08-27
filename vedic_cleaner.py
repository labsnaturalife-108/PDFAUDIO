import re
from typing import Dict, Any

class VedicTextCleaner:
    @classmethod
    def clean(cls, raw_text: str) -> str:
        """
        Cleans Vedic scriptures (Srimad-Bhagavatam, Bhagavad-gita, etc.)
        by removing Sanskrit transliterations and word-by-word vocabulary lines,
        preserving Chapter titles, Text numbers, Russian literary translations,
        and commentaries. Also fixes common OCR scanner typos.
        """
        if not raw_text or not raw_text.strip():
            return ""

        text = raw_text

        # 1. Fix common scanner OCR typos in Russian letters (e.g. 'д' instead of 'ъ')
        text = re.sub(r'обдясн', 'объясн', text, flags=re.IGNORECASE)
        text = re.sub(r'неотдемлем', 'неотъемлем', text, flags=re.IGNORECASE)
        text = re.sub(r'обдектом', 'объектом', text, flags=re.IGNORECASE)
        text = re.sub(r'обдект', 'объект', text, flags=re.IGNORECASE)
        text = re.sub(r'издянов', 'изъянов', text, flags=re.IGNORECASE)
        text = re.sub(r'раздясн', 'разъясн', text, flags=re.IGNORECASE)

        # 2. Normalize Latin letters inserted into Russian words (homoglyphs)
        homoglyphs = {
            'a': 'а', 'e': 'е', 'o': 'о', 'p': 'р', 'c': 'с', 'y': 'у', 'x': 'х',
            'A': 'А', 'E': 'Е', 'O': 'О', 'P': 'Р', 'C': 'С', 'T': 'Т', 'H': 'Н',
            'M': 'М', 'B': 'В', 'K': 'К', 'X': 'Х'
        }
        for lat, cyr in homoglyphs.items():
            text = text.replace(lat, cyr)

        # 3. Split by ТЕКСТ / ТЕКСТЫ / TEXT / ШЛОКА markers
        text_split_pattern = r'((?:^|\n)[ \t]*(?:ТЕКСТ(?:Ы)?|TEXT|ШЛОКА)[ \t]*[\d─–-]+[^\r\n]*)'
        splits = re.split(text_split_pattern, text, flags=re.IGNORECASE)

        output_chunks = []
        # First chunk before any ТЕКСТ (e.g. Chapter title or Book header)
        if splits and splits[0].strip():
            output_chunks.append(splits[0].strip())

        for i in range(1, len(splits), 2):
            header = splits[i].strip()
            content = splits[i+1] if i+1 < len(splits) else ''

            # Separate commentary if present
            comm_match = re.search(r'(\n\s*КОММЕНТ[АA]РИЙ\s*:.*)', content, flags=re.DOTALL | re.IGNORECASE)
            commentary = ''
            verse_section = content
            if comm_match:
                commentary = comm_match.group(1).rstrip()
                verse_section = content[:comm_match.start()]

            # Split paragraphs inside verse section
            paras = [p.strip() for p in verse_section.split('\n\n') if p.strip()]

            # Find word-by-word translation paragraph
            wbw_idx = -1
            for idx, p in enumerate(paras):
                semi_count = p.count(';')
                dash_count = p.count('—') + p.count('-')
                # Word-by-word lines have multiple definitions separated by semicolons and dashes
                if (semi_count >= 1 and dash_count >= 2) or semi_count >= 3:
                    wbw_idx = idx
                    break

            if wbw_idx != -1:
                # All paragraphs AFTER word-by-word are the Russian literary translation
                literary_paras = paras[wbw_idx + 1:]
            else:
                # If no word-by-word was found (e.g. already cleaned or prose),
                # filter out short sanskrit verse lines that don't end with standard punctuation
                literary_paras = []
                for p in paras:
                    lines = [l.strip() for l in p.split('\n') if l.strip()]
                    if len(lines) >= 2 and not any(p.endswith(end_punct) for end_punct in ['.', '!', '?', '»', '”', ':']):
                        continue
                    literary_paras.append(p)

            literary_translation = '\n\n'.join(literary_paras).strip()

            block_res = f'{header}\n\n{literary_translation}{commentary}'
            output_chunks.append(block_res.strip())

        return '\n\n\n'.join(output_chunks).strip()

    @classmethod
    def clean_with_stats(cls, raw_text: str) -> Dict[str, Any]:
        cleaned = cls.clean(raw_text)
        orig_len = len(raw_text)
        clean_len = len(cleaned)
        removed_len = max(0, orig_len - clean_len)
        pct_removed = round((removed_len / orig_len * 100) if orig_len > 0 else 0, 1)

        return {
            "original_chars": orig_len,
            "cleaned_chars": clean_len,
            "removed_chars": removed_len,
            "percent_removed": pct_removed,
            "cleaned_text": cleaned
        }
