# Enterprise AI Knowledge Assistant

A local-first RAG application for asking questions across company documents. It supports PDF, DOCX, CSV and TXT uploads, semantic retrieval, Gemini-generated answers, source metadata, chat history, document deletion, a FastAPI backend and a Streamlit UI.

## 1. Requirements

- Python 3.11 or 3.12
- A Gemini API key (use a free quota if available in your region/account)
- Internet access on first run to install packages and download the embedding model

The app itself can run locally without paid hosting, PostgreSQL, or a paid vector database. SQLite and ChromaDB persist data on your computer. Google API quotas, model availability and free-tier terms can change.

## 2. Project structure

```text
enterprise-ai-knowledge-assistant/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── ingestion.py
│   ├── rag_pipeline.py
│   └── database.py
├── frontend/
│   └── app.py
├── evaluation/
│   ├── evaluate.py
│   ├── evaluate_api.py
│   └── rag_test_dataset.json
├── data/                  # Local runtime data; excluded from Git
│   ├── uploads/
│   ├── chroma_db/
│   └── app.db
├── hr_policy.txt
├── it_policy.txt
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md

## 3. Windows setup (PowerShell)

Open PowerShell in the project directory:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Put your key after `GEMINI_API_KEY=` and save the file. Do not add quotes or commit `.env` to Git.

If PowerShell blocks activation, you do not need to activate the environment; use `.\venv\Scripts\python.exe` and `.\venv\Scripts\streamlit.exe` as shown below.

## 4. Run the application

Terminal 1 — API:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Check:
- API health: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs

Terminal 2 — frontend:

```powershell
.\venv\Scripts\python.exe -m streamlit run frontend/app.py
```

Open the Streamlit URL printed in the terminal (normally http://localhost:8501).

On first use, Sentence Transformers downloads `all-MiniLM-L6-v2`. This is a one-time model download and does not require a paid API.

## 5. API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/upload` | Upload and index one document |
| POST | `/ask` | Ask a question (`question`, optional `top_k`) |
| GET | `/documents` | List indexed documents |
| DELETE | `/documents/{filename}` | Delete a document and its vectors |
| GET | `/history` | Read saved Q&A |
| DELETE | `/history` | Clear saved Q&A |

Example request:

```json
{
  "question": "What is the company's leave policy?",
  "top_k": 5
}
```

## 6. Evaluation

Upload a sample document, then edit `TEST_CASES` in `evaluation/evaluate.py` with questions and the expected source filename. Run:

```powershell
.\venv\Scripts\python.exe evaluation/evaluate.py
```

The script reports Hit@5 and Mean Reciprocal Rank (MRR) for retrieval. These are retrieval metrics, not a full RAGAS faithfulness score. For a formal RAGAS evaluation, create a labelled question/ground-truth dataset and run RAGAS separately; it is not installed by default to keep the initial setup lighter.

## 7. Notes and limitations

- PDF page numbers are extracted from the original PDF. DOCX does not expose stable page numbers through this parser, so its source is shown with page unavailable. CSV sources show row numbers.
- Scanned/image-only PDFs need OCR; this version reports that no readable text was found.
- The similarity threshold is a practical starting point, not a calibrated confidence score. Validate it with your own documents and evaluation questions.
- The API is intended for local development. Before exposing it to a company network or the public, add authentication, user/tenant permissions, upload malware scanning, rate limits, HTTPS, and stricter CORS.
- Deleting a document removes its uploaded file, metadata record and Chroma vectors. It does not remove previous chat-history answers that may quote that document; clear chat history when required.
- ChromaDB and SQLite files are stored under `data/`. Back up this directory to preserve your local knowledge base.

## 8. Docker

Build and run from the project root:

```bash
docker build -t enterprise-knowledge-assistant .
docker run --rm -p 8000:8000 -p 8501:8501 --env-file .env -v "$(pwd)/data:/app/data" enterprise-knowledge-assistant
```

On Windows PowerShell, replace `$(pwd)` with `${PWD}` if needed:

```powershell
docker run --rm -p 8000:8000 -p 8501:8501 --env-file .env -v "${PWD}/data:/app/data" enterprise-knowledge-assistant
```

## 9. Security

Keep `.env` private. Do not upload confidential company documents to a demo without permission. Gemini receives retrieved text snippets to generate answers; review your organization's data-handling requirements before using real employee or confidential records.
