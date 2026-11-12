import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
#----#
import json
import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from backend.database import (
    init_db, save_document, list_documents, delete_document_record,
    add_chat, get_history, clear_history
)
from backend.rag_pipeline import (
    UPLOAD_DIR, index_document, answer_question, delete_document_vectors
)

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt"}

app = FastAPI(
    title="Enterprise AI Knowledge Assistant",
    description="Private document Q&A using retrieval-augmented generation.",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
def startup():
    init_db()

class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)

@app.get("/")
def root():
    return {"message": "Enterprise AI Knowledge Assistant API", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Supported formats: PDF, DOCX, CSV, TXT.")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_MB} MB limit.")
    safe_name = filename
    try:
        chunk_count = index_document(safe_name, content)
        target = UPLOAD_DIR / safe_name
        target.write_bytes(content)
        save_document(safe_name, extension.lstrip("."), len(content), chunk_count)
        return {"message": "Document uploaded and indexed successfully.",
                "filename": safe_name, "total_chunks": chunk_count}
    except Exception as exc:
        # Avoid exposing internal stack traces to API clients.
        raise HTTPException(500, f"Could not process document: {exc}") from exc



@app.post("/ask")
def ask(request: AskRequest):
    try:
        result = answer_question(request.question.strip(), request.top_k)
        add_chat(
            request.question.strip(),
            result["answer"],
            json.dumps(result["sources"])
        )
        return result

    except RuntimeError as exc:
        logger.exception("RAG runtime error")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    except Exception as exc:
        logger.exception("Question processing failed")
        error_text = str(exc)

        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            raise HTTPException(
                status_code=429,
                detail="Gemini API quota exhausted. Please check your AI Studio usage and retry when quota resets."
            ) from exc

        raise HTTPException(
            status_code=500,
            detail=f"Question processing failed: {error_text}"
        ) from exc

@app.get("/documents")
def documents():
    return {"documents": list_documents()}

@app.delete("/documents/{filename}")
def delete_document(filename: str):
    # filename is URL-decoded by FastAPI; only permit a basename.
    if Path(filename).name != filename:
        raise HTTPException(400, "Invalid filename.")
    try:
        delete_document_vectors(filename)
        file_path = UPLOAD_DIR / filename
        if file_path.exists():
            file_path.unlink()
        delete_document_record(filename)
        return {"message": f"Deleted {filename} from the knowledge base."}
    except Exception as exc:
        raise HTTPException(500, f"Could not delete document: {exc}") from exc

@app.get("/history")
def history(limit: int = 50):
    return {"history": get_history(max(1, min(limit, 200)))}

@app.delete("/history")
def remove_history():
    clear_history()
    return {"message": "Chat history cleared."}
