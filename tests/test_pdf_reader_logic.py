"""Targeted tests for PDF OCR/vision decision logic."""
import importlib
import sys
import types

try:
    from app.services.ingestion.pdf_reader import PDFReader
except Exception:
    llama_index = types.ModuleType("llama_index")
    core = types.ModuleType("llama_index.core")
    schema = types.ModuleType("llama_index.core.schema")

    class Document:  # pragma: no cover - compatibility stub
        def __init__(self, text, metadata=None):
            self.text = text
            self.metadata = metadata or {}

    schema.Document = Document
    core.schema = schema
    llama_index.core = core
    sys.modules["llama_index"] = llama_index
    sys.modules["llama_index.core"] = core
    sys.modules["llama_index.core.schema"] = schema
    from app.services.ingestion.pdf_reader import PDFReader


class FakePage:
    def __init__(self, images):
        self.images = images


def test_merge_page_text_prefers_combined_content():
    reader = PDFReader()
    merged = reader._merge_page_text("Existing text", "Chart shows revenue rising 20%.")
    assert "Existing text" in merged
    assert "Chart shows revenue rising 20%." in merged
    assert "[visual extraction]" in merged


def test_merge_page_text_skips_empty_visual_text():
    reader = PDFReader()
    assert reader._merge_page_text("Existing text", "") == "Existing text"


def test_should_run_vision_disabled(monkeypatch):
    pdf_reader_module = importlib.import_module("app.services.ingestion.pdf_reader")

    monkeypatch.setattr(pdf_reader_module.settings, "PDF_VISION_ENABLED", False)
    reader = PDFReader()
    assert reader._should_run_vision(FakePage(images=[object()]), "", 1) is False


def test_should_run_vision_for_image_heavy_low_text(monkeypatch):
    pdf_reader_module = importlib.import_module("app.services.ingestion.pdf_reader")

    monkeypatch.setattr(pdf_reader_module.settings, "PDF_VISION_ENABLED", True)
    monkeypatch.setattr(pdf_reader_module.settings, "PDF_VISION_MAX_PAGES", 3)
    monkeypatch.setattr(pdf_reader_module.settings, "PDF_VISION_MIN_TEXT_CHARS", 80)
    monkeypatch.setattr(pdf_reader_module.settings, "PDF_VISION_MIN_IMAGE_COUNT", 1)
    reader = PDFReader()
    assert reader._should_run_vision(FakePage(images=[object()]), "short", 1) is True
