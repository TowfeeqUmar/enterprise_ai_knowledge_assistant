import csv
import io
import re
from pathlib import Path
from typing import Any
import fitz  # PyMuPDF
from docx import Document

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt"}

def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def extract_pages(filename: str, content: bytes) -> list[dict[str, Any]]:
    """Return text units with source-location metadata."""
    ext = Path(filename).suffix.lower()
    units = []

    if ext == ".pdf":
        with fitz.open(stream=content, filetype="pdf") as pdf:
            for page_no, page in enumerate(pdf, start=1):
                text = _clean(page.get_text("text"))
                if text:
                    units.append({"text": text, "page": page_no})
    elif ext == ".docx":
        doc = Document(io.BytesIO(content))
        parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                parts.append(paragraph.text.strip())
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))
        text = _clean("\n".join(parts))
        if text:
            units.append({"text": text, "page": None})
    elif ext == ".csv":
        decoded = content.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(decoded))
        rows = list(reader)
        if rows:
            headers = rows[0]
            for index, row in enumerate(rows[1:], start=2):
                if not any(str(cell).strip() for cell in row):
                    continue
                values = []
                for col, value in zip(headers, row):
                    values.append(f"{col}: {value}")
                units.append({"text": _clean(" | ".join(values)), "page": None,
                              "row_start": index, "row_end": index})
    elif ext == ".txt":
        text = _clean(content.decode("utf-8-sig", errors="replace"))
        if text:
            units.append({"text": text, "page": None})
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    if not units:
        raise ValueError("No readable text was found. The file may be empty or scanned.")
    return units

def chunk_units(units: list[dict[str, Any]], chunk_size: int = 1100,
                overlap: int = 180) -> list[dict[str, Any]]:
    """Split text while retaining PDF page / CSV row provenance."""
    chunks = []
    for unit in units:
        text = unit["text"]
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                split_at = text.rfind(" ", start + int(chunk_size * 0.65), end)
                if split_at > start:
                    end = split_at
            piece = text[start:end].strip()
            if piece:
                item = {"text": piece}
                if unit.get("page") is not None:
                    item["page"] = unit["page"]
                if unit.get("row_start") is not None:
                    item["row_start"] = unit["row_start"]
                    item["row_end"] = unit["row_end"]
                chunks.append(item)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks

def process_document(filename: str, content: bytes) -> list[dict[str, Any]]:
    return chunk_units(extract_pages(filename, content))
