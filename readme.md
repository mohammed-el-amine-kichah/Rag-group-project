# 🛠️ Ministry RAG Setup & Run Guide (Backend + Frontend)

This guide assumes you're starting from scratch. It sets up:

- 🧠 RAG backend (Python, FastAPI, Gemini)
- 💬 React frontend (Vite + Tailwind)

---

## 📦 Step 1: Clone the repository

```bash
git clone https://github.com/Iyed-Mouhoub/Ministry-Regulation-Q-A-System.git
cd Ministry-Regulation-Q-A-System
```

---

## 🧠 Step 2: Setup Python Backend (RAG)

### 1. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install backend requirements

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the project root:

```env
VECTOR_STORE_PATH=vector_store
EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
GEMINI_API_KEY=your_gemini_api_key_here
CHUNK_SIZE=500
MEMORY_SIZE=10
DATABASE_URL=postgresql://....
```

### 4. Run once to generate vector store

```bash
python -m rag.main
```

This creates the `vector_store/` folder based on `data/*.docx` or `data/*.txt` files.

---

### 5. Start the backend API

```bash
uvicorn backend.api:app --reload
```

Your RAG API is now running at `http://localhost:8000`

---

## 💬 Step 3: Setup Frontend (React)

### 1. Go to frontend folder

```bash
cd frontend
```

### 2. Install frontend dependencies

```bash
npm install
```

### 3. Set up frontend environment

Create a file named `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### 4. Start the frontend dev server

```bash
npm run dev
```

Open your browser to `http://localhost:5173`

---

## ✅ Final Test

- Type a question in Arabic.
- Your message should go to `http://localhost:8000/chat`.
- You should receive a model-generated answer in return.

---

## 🔁 Adding new documents (scaling up)

To ingest a new DOCX or TXT file:

1. Place it inside the `data/` folder.
2. Either:

   - Rerun: `python -m rag.main`
   - Or expose `/upload` endpoint and hit it from frontend.

---

## 📁 Project Structure Summary

```bash
Ministry-Regulation-Q-A-System/
├── backend/               # FastAPI app (api.py)
├── rag/                   # RAG pipeline code
├── vector_store/          # FAISS index (auto)
├── data/                  # DOCX/TXT source files
├── frontend/              # React app (Vite)
├── requirements.txt
└── .env
```

You're now ready to use and extend the system!
