import os
import hashlib
from pathlib import Path
from typing import Any
import chromadb
from sentence_transformers import SentenceTransformer
from google import genai
from google.genai import types
from dotenv import load_dotenv

from backend.ingestion import process_document

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma_db"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(BASE_DIR / ".env")

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
COLLECTION_NAME = "enterprise_knowledge"
_embedding_model = None
_chroma_client = None
_collection = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model

def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def _embed(texts: list[str]):
    vectors = get_embedding_model().encode(
        texts, normalize_embeddings=True, show_progress_bar=False
    )
    return vectors.tolist()

def index_document(filename: str, content: bytes) -> int:
    chunks = process_document(filename, content)
    collection = get_collection()
    # Re-uploading a filename replaces its old vectors.
    delete_document_vectors(filename)
    ids, texts, metadatas = [], [], []
    for index, chunk in enumerate(chunks):
        raw_id = f"{filename}:{index}"
        chunk_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
        metadata = {"filename": filename, "chunk_index": index}
        if chunk.get("page") is not None:
            metadata["page"] = int(chunk["page"])
        if chunk.get("row_start") is not None:
            metadata["row_start"] = int(chunk["row_start"])
            metadata["row_end"] = int(chunk["row_end"])
        ids.append(chunk_id)
        texts.append(chunk["text"])
        metadatas.append(metadata)
    embeddings = _embed(texts)
    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    return len(chunks)

def delete_document_vectors(filename: str):
    collection = get_collection()
    collection.delete(where={"filename": filename})

def retrieve(question: str, top_k: int = 5, min_similarity: float = 0.20):
    collection = get_collection()
    if collection.count() == 0:
        return []
    query_embedding = _embed([question])[0]
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(max(1, top_k), collection.count()),
        include=["documents", "metadatas", "distances"]
    )
    matches = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    for doc, meta, distance in zip(docs, metas, distances):
        similarity = 1.0 - float(distance)
        if similarity >= min_similarity:
            matches.append({"text": doc, "metadata": meta, "similarity": round(similarity, 4)})
    return matches

def _source_label(meta: dict[str, Any]) -> str:
    label = meta.get("filename", "Unknown document")
    if meta.get("page"):
        label += f", page {meta['page']}"
    elif meta.get("row_start"):
        label += f", row {meta['row_start']}"
    else:
        label += ", page unavailable"
    return label


def answer_question(question: str, top_k: int = 5) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to the .env file."
        )

    matches = retrieve(question, top_k=top_k)

    abstention_text = (
        "I couldn't find this information in the uploaded documents."
    )

    if not matches:
        return {
            "answer": abstention_text,
            "sources": [],
            "found": False
        }

    context_parts = []
    sources = []

    for i, match in enumerate(matches, start=1):
        meta = match["metadata"]
        label = _source_label(meta)

        context_parts.append(
            f"[SOURCE {i}: {label}]\n{match['text']}"
        )

        sources.append({
            "filename": meta.get("filename"),
            "page": meta.get("page"),
            "row_start": meta.get("row_start"),
            "chunk_index": meta.get("chunk_index"),
            "similarity": match["similarity"],
            "excerpt": match["text"][:500]
        })

    prompt = f"""You are a careful enterprise document assistant.

Answer the employee's question using ONLY the supplied context.

Rules:
- Do not use outside knowledge or make assumptions.
- If the context does not contain enough evidence to answer,
  respond with exactly:
  "{abstention_text}"
- Cite supporting sources inline using [Source 1], [Source 2], etc.
- If sources conflict, clearly explain the conflict and cite both.
- Be concise and distinguish explicit policy from inference.

CONTEXT:
{chr(10).join(context_parts)}

QUESTION:
{question}

ANSWER:"""

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1)
    )

    answer = (response.text or "").strip()

    if not answer:
        answer = (
            "I couldn't generate a reliable answer "
            "from the retrieved documents."
        )

    # Detect an explicit abstention from Gemini.
    if abstention_text.casefold() in answer.casefold():
        return {
            "answer": answer,
            "sources": [],
            "found": False
        }

    return {
        "answer": answer,
        "sources": sources,
        "found": True
    }
