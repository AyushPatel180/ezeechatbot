"""PDF ingestion using pdfplumber with optional OCR fallback for image-heavy pages."""
import base64
import io
from typing import List

import pdfplumber
from llama_index.core.schema import Document

from app.config import settings
from app.services.ingestion.vision_page_extractor import extract_page_with_vision

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None
    TesseractNotFoundError = RuntimeError


class PDFReader:
    """Extract text from base64-encoded PDF with page-level metadata."""

    def _load_pdf_bytes(self, pdf_bytes: bytes, bot_id: str, api_key: str | None = None) -> List[Document]:
        pdf_stream = io.BytesIO(pdf_bytes)
        documents = []
        with pdfplumber.open(pdf_stream) as pdf:
            total_pages = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                extraction_method = "text"

                if self._should_run_ocr(page, text, page_num):
                    ocr_text = self._ocr_page(page)
                    if len(ocr_text) > len(text.strip()):
                        text = ocr_text
                        extraction_method = "ocr"

                if self._should_run_vision(page, text, page_num):
                    vision_text = extract_page_with_vision(page, api_key=api_key)
                    merged_text = self._merge_page_text(text, vision_text)
                    if merged_text != text:
                        text = merged_text
                        extraction_method = (
                            "ocr+vision" if extraction_method == "ocr" else "text+vision"
                        )

                if text and text.strip():
                    doc = Document(
                        text=text.strip(),
                        metadata={
                            "bot_id": bot_id,
                            "page_number": page_num,
                            "total_pages": total_pages,
                            "source_type": "pdf",
                            "extraction_method": extraction_method,
                            "image_count": len(getattr(page, "images", []) or []),
                        }
                    )
                    doc.excluded_embed_metadata_keys = ["bot_id"]
                    documents.append(doc)
        return documents

    def _should_run_ocr(self, page, extracted_text: str, page_num: int) -> bool:
        if not settings.PDF_OCR_ENABLED:
            return False
        if pytesseract is None:
            return False
        if page_num > settings.PDF_OCR_MAX_PAGES:
            return False
        if len((extracted_text or "").strip()) >= settings.PDF_OCR_MIN_TEXT_CHARS:
            return False
        return len(getattr(page, "images", []) or []) >= settings.PDF_OCR_MIN_IMAGE_COUNT

    def _ocr_page(self, page) -> str:
        page_image = page.to_image(resolution=settings.PDF_OCR_RENDER_DPI)
        pil_image = page_image.original
        try:
            text = pytesseract.image_to_string(pil_image)
        except TesseractNotFoundError:
            return ""
        return text.strip()

    def _should_run_vision(self, page, extracted_text: str, page_num: int) -> bool:
        if not settings.PDF_VISION_ENABLED:
            return False
        if page_num > settings.PDF_VISION_MAX_PAGES:
            return False
        if len((extracted_text or "").strip()) >= settings.PDF_VISION_MIN_TEXT_CHARS:
            return False
        return len(getattr(page, "images", []) or []) >= settings.PDF_VISION_MIN_IMAGE_COUNT

    def _merge_page_text(self, base_text: str, fallback_text: str) -> str:
        base_text = (base_text or "").strip()
        fallback_text = (fallback_text or "").strip()
        if not fallback_text:
            return base_text
        if not base_text:
            return fallback_text
        if fallback_text in base_text:
            return base_text
        return f"{base_text}\n\n[visual extraction]\n{fallback_text}"
    
    def load(self, base64_content: str, bot_id: str, api_key: str | None = None) -> List[Document]:
        """
        Decode base64 PDF and extract text per page.
        
        Args:
            base64_content: Base64-encoded PDF data
            bot_id: Bot identifier for metadata
            
        Returns:
            List of LlamaIndex Documents with page metadata
        """
        try:
            # Decode base64
            pdf_bytes = base64.b64decode(base64_content)
            return self._load_pdf_bytes(pdf_bytes, bot_id, api_key=api_key)
            
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {str(e)}")

    def load_bytes(self, pdf_bytes: bytes, bot_id: str, api_key: str | None = None) -> List[Document]:
        """Extract text from raw PDF bytes."""
        try:
            return self._load_pdf_bytes(pdf_bytes, bot_id, api_key=api_key)
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {str(e)}")


# Singleton instance
pdf_reader = PDFReader()
