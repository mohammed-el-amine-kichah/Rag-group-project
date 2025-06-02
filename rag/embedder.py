# rag/embedder.py

from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from rag.settings import EMBEDDING_MODEL_NAME

embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

def embed_chunks(chunks: list) -> list:
    embeddings = []
    print(f"\n🧠 Embedding {len(chunks)} chunks...")
    for chunk in tqdm(chunks, desc="Generating embeddings", unit="chunk"):
        embedding = embedder.encode(chunk)
        embeddings.append(embedding)
    return embeddings
