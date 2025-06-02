# rag/ingestion.py
import os
from typing import List, Tuple
from rag.file_converter import extract_text   # now handles DOCX / TXT only

def ingest_documents(folder_path: str,
                     file_whitelist: List[str] | None = None
                     ) -> List[Tuple[str, str]]:
    """
    Read .docx (and plain .txt) files in *folder_path* and return (filename, text) pairs.
    """
    supported_ext = {".docx", ".txt"}        # ⬅️  PDFs removed
    texts: list[Tuple[str, str]] = []

    for filename in os.listdir(folder_path):
        if file_whitelist and filename not in file_whitelist:
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in supported_ext:
            continue

        try:
            file_path = os.path.join(folder_path, filename)
            text = extract_text(file_path) if ext == ".docx" else open(
                file_path, "r", encoding="utf-8").read()

            if text.strip():
                texts.append((filename, text))
        except Exception as e:
            print(f"[INGEST ERROR] {filename}: {e}")

    return texts
