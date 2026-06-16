from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from pptx import Presentation
from pypdf import PdfReader


def parse_document(filename: str, content: bytes) -> list[tuple[int | None, str]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(content))
        return [
            (index + 1, page.extract_text() or "")
            for index, page in enumerate(reader.pages)
            if (page.extract_text() or "").strip()
        ]

    if suffix == ".docx":
        doc = DocxDocument(BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
        return [(None, text)] if text.strip() else []

    if suffix == ".pptx":
        deck = Presentation(BytesIO(content))
        pages: list[tuple[int | None, str]] = []
        for index, slide in enumerate(deck.slides):
            texts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append(shape.text)
            if texts:
                pages.append((index + 1, "\n".join(texts)))
        return pages

    raise ValueError("Unsupported file type. Upload PDF, DOCX, or PPTX.")


def recursive_chunk(text: str, max_chars: int = 1200, overlap: int = 180) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + max_chars, len(clean))
        if end < len(clean):
            split_at = max(clean.rfind(". ", start, end), clean.rfind("\n", start, end))
            if split_at > start + max_chars // 2:
                end = split_at + 1
        chunks.append(clean[start:end].strip())
        if end == len(clean):
            break
        start = max(0, end - overlap)
    return chunks
