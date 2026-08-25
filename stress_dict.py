import json
import re
from pathlib import Path
from typing import Dict, Optional
from config import DICTIONARIES_DIR

class StressDictionary:
    def __init__(self, dict_path: Optional[Path] = None):
        self.dict_path = dict_path or (DICTIONARIES_DIR / "default.json")
        self.entries: Dict[str, str] = {}
        self.load()

    def load(self) -> None:
        if self.dict_path.exists():
            with open(self.dict_path, "r", encoding="utf-8") as f:
                self.entries = json.load(f)
        else:
            self.entries = {}

    def save(self, path: Optional[Path] = None) -> None:
        target = path or self.dict_path
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def add_entry(self, word: str, replacement: str) -> None:
        self.entries[word.strip()] = replacement.strip()
        self.save()

    def remove_entry(self, word: str) -> bool:
        word = word.strip()
        if word in self.entries:
            del self.entries[word]
            self.save()
            return True
        return False

    def update_all(self, new_entries: Dict[str, str]) -> None:
        self.entries = {k.strip(): v.strip() for k, v in new_entries.items() if k.strip()}
        self.save()

    def apply(self, text: str) -> str:
        """
        Applies dictionary replacements preserving Russian word boundaries,
        accents (\u0300-\u036f), and capitalization.
        """
        if not text or not self.entries:
            return text

        result = text
        # Sort keys by length descending to replace compound phrases / longer words first
        sorted_words = sorted(self.entries.keys(), key=len, reverse=True)

        for word in sorted_words:
            replacement = self.entries[word]
            # Boundary pattern includes Cyrillic letters, digits and combining accents
            pattern = rf"(?<![а-яА-ЯёЁ0-9\u0300-\u036f]){re.escape(word)}(?![а-яА-ЯёЁ0-9\u0300-\u036f])"
            
            def replace_match(m: re.Match) -> str:
                matched_text = m.group(0)
                if matched_text and matched_text[0].isupper():
                    return replacement[0].upper() + replacement[1:]
                return replacement.lower()

            result = re.sub(pattern, replace_match, result, flags=re.IGNORECASE)

        return result
