import re
from typing import List

class TextChunker:
    @staticmethod
    def split_into_chunks(text: str, max_chunk_len: int = 1000) -> List[str]:
        if not text:
            return []

        # Normalize line endings
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split into sentences keeping punctuation attached
        # Regex splits after . ! ? … followed by whitespace or newline
        sentences = re.split(r"(?<=[.!?…])\s+", normalized)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            # If a single sentence exceeds max_chunk_len, split it by commas/semicolons or sub-clauses
            if len(sentence) > max_chunk_len:
                sub_parts = TextChunker._split_long_sentence(sentence, max_chunk_len)
                for part in sub_parts:
                    if current_chunk and (len(current_chunk) + len(part) + 1 > max_chunk_len):
                        chunks.append(current_chunk)
                        current_chunk = part
                    else:
                        if current_chunk:
                            current_chunk += " " + part
                        else:
                            current_chunk = part
                continue

            if current_chunk and (len(current_chunk) + len(sentence) + 1 > max_chunk_len):
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    @staticmethod
    def _split_long_sentence(sentence: str, max_len: int) -> List[str]:
        # Try splitting by comma, semicolon, colon, or dash
        parts = re.split(r"(?<=[,;:\—\–])\s+", sentence)
        sub_chunks: List[str] = []
        current = ""

        for p in parts:
            if not p.strip():
                continue
            if current and (len(current) + len(p) + 1 > max_len):
                sub_chunks.append(current)
                current = p
            else:
                if current:
                    current += " " + p
                else:
                    current = p

        if current:
            sub_chunks.append(current)

        return sub_chunks if sub_chunks else [sentence]
