# Enterprise AI Knowledge Assistant

A local-first Enterprise AI Knowledge Assistant built using Retrieval-Augmented Generation (RAG). Upload company documents and ask questions using natural language. Answers are grounded in retrieved document content and include source citations.

## Features

- Upload PDF, DOCX, CSV, and TXT documents.
- Extract and split document content into chunks.
- Generate embeddings using Sentence Transformers.
- Store and retrieve document vectors using ChromaDB.
- Generate grounded answers using the Google Gemini API.
- Include source citations in generated answers.
- Abstain when relevant information is not found.
- View and delete indexed documents.
- Maintain chat history using SQLite.
- FastAPI backend and Streamlit frontend.
- Retrieval and answer evaluation scripts.

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python |
| Backend | FastAPI |
| Frontend | Streamlit |
| LLM | Google Gemini API |
| Embeddings | Sentence Transformers |
| Vector database | ChromaDB |
| Metadata and chat storage | SQLite |
| Document processing | PyMuPDF, python-docx |
| API testing | Python urllib |

## Project Structure

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
├── .dockerignore
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

## Requirements

- Python 3.11 or 3.12
- Google Gemini API key
- Internet access for package installation, embedding-model download, and Gemini requests

The application stores its vector database and metadata locally. No paid vector database or hosted application platform is required for local development.

Gemini model availability, request limits, and free-tier quotas depend on Google's current service and account terms.

## Windows Installation

Open PowerShell in the project root directory.

### 1. Create a virtual environment

```powershell
python -m venv venv
```

### 2. Install dependencies

```powershell
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
notepad .env
```

Add your Gemini API key:

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
MAX_UPLOAD_MB=25
API_URL=http://127.0.0.1:8000
```

Save the file.

**Security:** Never commit `.env` or share your API key. The repository includes `.env.example` as a configuration template.

If PowerShell blocks virtual-environment activation, use the explicit Python executable commands shown in this README. Activation is not required.

## Run the Application

Run the backend and frontend in separate PowerShell terminals.

### Terminal 1 — FastAPI backend

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

API health check:

```text
http://127.0.0.1:8000/health
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

### Terminal 2 — Streamlit frontend

```powershell
.\venv\Scripts\python.exe -m streamlit run frontend/app.py
```

Open the local URL printed by Streamlit, normally:

```text
http://localhost:8501
```

On first run, Sentence Transformers downloads the configured embedding model. This download is separate from Gemini API generation requests.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Root endpoint |
| GET | `/health` | Backend health check |
| POST | `/upload` | Upload and index a document |
| POST | `/ask` | Ask a question |
| GET | `/documents` | List indexed documents |
| DELETE | `/documents/{filename}` | Delete a document and its vectors |
| GET | `/history` | Retrieve chat history |
| DELETE | `/history` | Clear chat history |

Example question request:

```json
{
  "question": "What is the company's leave policy?",
  "top_k": 5
}
```

The `top_k` parameter controls how many document chunks are retrieved.

## Evaluation

The project includes separate retrieval and end-to-end API evaluation scripts.

### 1. Retrieval evaluation

Start with:

```powershell
.\venv\Scripts\python.exe evaluation\evaluate.py
```

This evaluates document retrieval using:

- **Hit@5:** Whether the expected source document appears in the top five retrieved results.
- **Mean Reciprocal Rank (MRR):** How highly the expected document is ranked.

These metrics evaluate retrieval quality, not the factual correctness of generated answers.

### 2. Answer and citation evaluation

Start the FastAPI backend, then run:

```powershell
.\venv\Scripts\python.exe evaluation\evaluate_api.py
```

This evaluates:

- Expected answer content.
- Whether the answer cites the expected source document.
- Whether unsupported questions are correctly rejected.
- API errors and incomplete requests.

The API evaluation calls Gemini and therefore depends on API availability and quota. HTTP 429 indicates a quota or rate-limit response; HTTP 503 indicates temporary service unavailability.

Requests that fail because of API errors are incomplete tests, not evidence of incorrect document retrieval. Rerun the evaluation when the service is available.

## Sample Evaluation Results

A local retrieval evaluation during development produced:

| Metric | Result |
|---|---:|
| Hit@5 | 100% |
| MRR | 1.000 |
| Retrieval questions | 8 |

These are development results on the included sample policy documents, not a guarantee of performance on arbitrary company documents.

## Docker

Build the image from the project root:

```bash
docker build -t enterprise-knowledge-assistant .
```

Run the container:

```bash
docker run --rm -p 8000:8000 -p 8501:8501 --env-file .env -v enterprise-data:/app/data enterprise-knowledge-assistant
```

The named Docker volume preserves application data between container runs.

The container starts both the FastAPI backend and Streamlit frontend for demonstration purposes. For production deployments, run the services separately and configure appropriate process management, health checks, authentication, and networking.

The `.dockerignore` file excludes local secrets, virtual environments, and runtime data from the build context.

## Limitations

- Gemini API access requires a valid API key and is subject to model availability, quotas, and rate limits.
- Scanned or image-only PDFs require OCR, which is not implemented in this version.
- DOCX documents do not provide stable page numbers through the current parser.
- CSV source references use row information rather than PDF page numbers.
- Similarity thresholds require validation against the documents and questions used in a real deployment.
- The included policy documents are sample data and should not be treated as real company policies.
- The current API is intended for local development and demonstration, not unrestricted public deployment.

## Security Considerations

- Keep API keys in `.env`; never commit secrets.
- Do not upload confidential company documents without authorization.
- Retrieved document text is sent to Gemini for answer generation. Review applicable data-handling and privacy requirements before using sensitive information.
- Before production use, implement authentication, authorization, tenant isolation, upload scanning, rate limiting, HTTPS, and appropriate CORS restrictions.
- Deleting a document removes its uploaded file, metadata, and indexed vectors. Existing chat history may still contain information from that document.

## Future Improvements

- Add OCR support for scanned PDFs.
- Improve evaluation with labelled datasets and additional RAG quality metrics.
- Add authentication and role-based access control.
- Support multi-user document collections.
- Add more robust monitoring and API retry handling.
