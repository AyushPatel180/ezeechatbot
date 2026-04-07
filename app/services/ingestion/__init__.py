"""Ingestion package — document readers for PDF, URL, and plain text."""
from app.services.ingestion.pdf_reader import pdf_reader, PDFReader
from app.services.ingestion.url_reader import url_reader, URLReader
from app.services.ingestion.text_reader import text_reader, TextReader

__all__ = [
    "pdf_reader",
    "PDFReader",
    "url_reader",
    "URLReader",
    "text_reader",
    "TextReader",
]
