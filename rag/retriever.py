import numpy as np
from rag.vector_store import VectorStore
from rag.embedder import embed_chunks

def retrieve_relevant_chunks(store: VectorStore, query: str, top_k: int = 5) -> list:
    query_embedding = embed_chunks([query])

    if isinstance(query_embedding[0], float):
        query_embedding = [query_embedding]

    query_vector = np.array(query_embedding, dtype='float32')

    results = store.search(query_vector[0], top_k)
    return [meta["content"] for meta in results]
