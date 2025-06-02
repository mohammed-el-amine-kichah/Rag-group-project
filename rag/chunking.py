# rag/chunking.py

from tqdm import tqdm
from rag.utils import clean_text, is_quality    

def chunk_text(text: str, chunk_size: int) -> list:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current_chunk = ""

    for para in tqdm(paragraphs, desc="Chunking paragraphs", unit="para"):
        if len(current_chunk) + len(para) <= chunk_size:
            current_chunk += " " + para
        else:
            chunks.append(current_chunk.strip())
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
