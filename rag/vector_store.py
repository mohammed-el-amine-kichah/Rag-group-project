# rag/vector_store.py
import os
import faiss
import pickle
import numpy as np

class VectorStore:
    def __init__(self, dimension: int, db_path="vector_store"):
        self.db_path = db_path
        self.index = faiss.IndexFlatL2(dimension)
        self.metadata = []

    def add(self, vectors, metadata):
        self.index.add(np.array(vectors).astype("float32"))
        self.metadata.extend(metadata)

    def save(self, path):
        os.makedirs(path, exist_ok=True)
        faiss.write_index(self.index, os.path.join(path, "index.faiss"))
        with open(os.path.join(path, "metadata.pkl"), "wb") as f:
            pickle.dump(self.metadata, f)

    @staticmethod
    def load(path):
        store = VectorStore(0)  # Dummy init
        store.index = faiss.read_index(os.path.join(path, "index.faiss"))
        with open(os.path.join(path, "metadata.pkl"), "rb") as f:
            store.metadata = pickle.load(f)
        return store
    def search(self, query_vector, top_k=5):
        distances, indices = self.index.search(np.array([query_vector]).astype("float32"), top_k)
        results = []
        for idx in indices[0]:
            if idx == -1:
                continue
            results.append(self.metadata[idx])
        return results