from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def extract_markdown_text(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore").strip()
