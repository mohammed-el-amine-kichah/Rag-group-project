# Updated rag/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "vector_store")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
LLM_PATH = os.getenv("LLM_PATH", "models/cohere-r7b-arabic-02-2025.gguf")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
HF_TOKEN = os.getenv("HF_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# New memory size setting
MEMORY_SIZE = int(os.getenv("MEMORY_SIZE", 10))
