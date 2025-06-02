# rag/main.py
import os
import json
from rag.settings import VECTOR_STORE_PATH, CHUNK_SIZE, MEMORY_SIZE
from rag.ingestion import ingest_documents
from rag.chunking import chunk_text
from rag.embedder import embed_chunks
from rag.vector_store import VectorStore
from rag.retriever import retrieve_relevant_chunks
from rag.agent import generate_answer


def load_processed_files(path: str) -> set:
    """Return a set of filenames that have already been embedded."""
    try:
        with open(os.path.join(path, "processed_files.json"), "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()


def save_processed_files(path: str, filenames: set):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "processed_files.json"), "w") as f:
        json.dump(list(filenames), f)


def build_or_update_store(files_to_process: set, index_path: str) -> VectorStore:
    """Read DOCX/TXT files, chunk, embed and append to FAISS index."""
    texts = ingest_documents("data", list(files_to_process))
    chunks: list[str] = []
    for _, txt in texts:
        chunks.extend(chunk_text(txt, CHUNK_SIZE))

    # Debug ‑ ensure we have useful chunks
    print(f"[DEBUG] Chunks kept after cleaning: {len(chunks)}")
    for c in chunks[:3]:
        print("[DEBUG sample]", c[:120], "...")

    if not chunks:
        raise RuntimeError("No chunks to embed – check cleaning thresholds or data directory.")

    print("\nGenerating embeddings…")
    vectors = embed_chunks(chunks)
    if not vectors:
        raise RuntimeError("Embedding returned empty list.")
    if isinstance(vectors[0], float):
        vectors = [vectors]

    metadata = [{"content": ch} for ch in chunks]
    embedding_dim = len(vectors[0])

    # create or load store
    if os.path.exists(index_path):
        store = VectorStore.load(VECTOR_STORE_PATH)
    else:
        store = VectorStore(dimension=embedding_dim)

    store.add(vectors, metadata)
    store.save(VECTOR_STORE_PATH)
    return store


def chat_loop(store: VectorStore):
    conversation_history: list[tuple[str, str]] = []
    print("\n📝 Enter your question in Arabic (or type 'exit'):")
    while True:
        query = input("\n📝 ")
        if query.lower() in {"exit", "quit", "خروج"}:
            print("\nمع السلامة!")
            break

        # Retrieve context
        top_chunks = retrieve_relevant_chunks(store, query, top_k=5)

        # Debug: show retrieved snippets
        print("\n--- retrieved chunks ---")
        for i, ch in enumerate(top_chunks, 1):
            print(f"{i}.", ch[:150], "…\n")

        # Generate answer
        answer = generate_answer(top_chunks, query, conversation_history)
        print(f"\n🗣️ {answer}\n")

        # Update conversation memory
        conversation_history.append((query, answer))
        if len(conversation_history) > MEMORY_SIZE:
            conversation_history = conversation_history[-MEMORY_SIZE:]


def main():
    index_path = os.path.join(VECTOR_STORE_PATH, "index.faiss")

    processed = load_processed_files(VECTOR_STORE_PATH)
    current_files = set(os.listdir("data"))
    new_files = current_files - processed

    if not os.path.exists(index_path):
        print("\n🆕 Building new vector store from all files…")
        files_to_process = current_files
        processed.clear()
        store = build_or_update_store(files_to_process, index_path)
        processed.update(files_to_process)
        save_processed_files(VECTOR_STORE_PATH, processed)
    elif new_files:
        print("\n📥 New files detected – updating store…")
        store = build_or_update_store(new_files, index_path)
        processed.update(new_files)
        save_processed_files(VECTOR_STORE_PATH, processed)
    else:
        print("\n✅ No new files – loading existing vector store…")
        store = VectorStore.load(VECTOR_STORE_PATH)

    # Start interaction loop
    chat_loop(store)


if __name__ == "__main__":
    main()
