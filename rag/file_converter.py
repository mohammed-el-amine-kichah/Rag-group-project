# rag/file_converter.py
import os
from docx import Document

def extract_text_from_docx(docx_path: str) -> str:
    """
    Read paragraphs from a DOCX and return a single cleaned string.
    """
    try:
        doc = Document(docx_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception as e:
        print(f"[DOCX ERROR] {e}")
        return ""

# ------------------------------------------------------------
# Public wrapper expected by ingestion.py
# ------------------------------------------------------------
def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return extract_text_from_docx(file_path)
    else:
        print(f"[UNSUPPORTED] {file_path}")
        return ""
