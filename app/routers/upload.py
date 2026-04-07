"""Upload router for knowledge base ingestion."""
import base64
import json
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError

from app.models import ContentType, UploadRequest, UploadResponse
from app.services.ingestion.pdf_reader import pdf_reader
from app.services.ingestion.url_reader import url_reader
from app.services.ingestion.text_reader import text_reader
from app.services.pipeline import ingest_documents
from app.db.stats_repo import create_bot_record
from app.utils.errors import NoExtractableContentError, IngestionError
from app.utils.logger import get_logger


router = APIRouter()
logger = get_logger(__name__)

LEGACY_SOURCE_TYPE_MAP = {
    "text": ContentType.text,
    "url": ContentType.website,
    "website": ContentType.website,
    "pdf_url": ContentType.pdf_url,
    "pdf_base64": ContentType.pdf_base64,
    "pdf_file": ContentType.pdf_file,
}


def _normalize_source_type(raw_source_type: Optional[str]) -> Optional[ContentType]:
    if raw_source_type is None:
        return None
    return LEGACY_SOURCE_TYPE_MAP.get(raw_source_type)


def _build_upload_request_from_body(body: dict) -> UploadRequest:
    raw_source_type = body.get("source_type") or body.get("content_type")
    source_type = _normalize_source_type(raw_source_type)
    if source_type is None:
        raise HTTPException(400, f"Unsupported source type: {raw_source_type}")

    payload = {
        "content_type": source_type,
        "text_content": body.get("text_content"),
        "website_url": body.get("website_url"),
        "pdf_url": body.get("pdf_url"),
        "pdf_base64_content": body.get("pdf_base64_content"),
        "metadata": body.get("metadata") or {},
    }

    legacy_content = body.get("content")
    if legacy_content:
        if source_type == ContentType.text and not payload["text_content"]:
            payload["text_content"] = legacy_content
        elif source_type == ContentType.website and not payload["website_url"]:
            payload["website_url"] = legacy_content
        elif source_type == ContentType.pdf_url and not payload["pdf_url"]:
            payload["pdf_url"] = legacy_content
        elif source_type == ContentType.pdf_base64 and not payload["pdf_base64_content"]:
            payload["pdf_base64_content"] = legacy_content

    try:
        return UploadRequest.model_validate(payload)
    except ValidationError as exc:
        detail = exc.errors()[0].get("msg", "Invalid request body")
        raise HTTPException(422, detail) from exc


async def _load_pdf_from_url(pdf_url: str, bot_id: str):
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"HTTP error fetching PDF URL: {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise ValueError(f"Request error fetching PDF URL: {str(exc)}") from exc

    pdf_bytes = response.content
    if not pdf_bytes:
        raise ValueError("Downloaded PDF is empty")
    return pdf_reader.load_bytes(pdf_bytes, bot_id)


@router.post("/upload", response_model=UploadResponse)
async def upload_knowledge_base(
    source_type: Optional[str] = Form(
        None,
        description="How you want to upload the knowledge base: `text`, `website`, `pdf_url`, `pdf_file`, or `pdf_base64`."
    ),
    text_content: Optional[str] = Form(None, description="Paste plain text content here."),
    website_url: Optional[str] = Form(None, description="Paste a public webpage URL here."),
    pdf_url: Optional[str] = Form(None, description="Paste a direct PDF URL here."),
    pdf_base64_content: Optional[str] = Form(None, description="Paste base64 PDF content here (advanced)."),
    pdf_file: Optional[UploadFile] = File(None, description="Upload a PDF file here."),
    metadata_json: str = Form("{}", description="Optional JSON metadata."),
    req: Request = None,
):
    """
    Upload a knowledge base (PDF file, URL, or plain text).
    
    Supports a single upload endpoint with multiple source types:
    - **text** -> provide `text_content`
    - **website** -> provide `website_url`
    - **pdf_url** -> provide `pdf_url`
    - **pdf_file** -> provide `pdf_file`
    - **pdf_base64** -> provide `pdf_base64_content`
    
    Returns a bot_id that can be used to query the chatbot.
    """
    bot_id = str(uuid.uuid4())
    client_ip = req.client.host if req.client else None

    upload_request: Optional[UploadRequest] = None
    if req.headers.get("content-type", "").startswith("application/json"):
        body = await req.json()
        upload_request = _build_upload_request_from_body(body)
        metadata_dict = upload_request.metadata or {}
    else:
        form = await req.form()
        raw_source_type = source_type or form.get("content_type")
        normalized_source_type = _normalize_source_type(raw_source_type)
        if normalized_source_type is None:
            raise HTTPException(400, f"Unsupported source type: {raw_source_type}")
        try:
            metadata_dict = json.loads(metadata_json or form.get("metadata") or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"Invalid metadata JSON: {exc.msg}") from exc

        payload = {
            "content_type": normalized_source_type,
            "text_content": text_content or form.get("content"),
            "website_url": website_url or (form.get("content") if normalized_source_type == ContentType.website else None),
            "pdf_url": pdf_url or (form.get("content") if normalized_source_type == ContentType.pdf_url else None),
            "pdf_base64_content": pdf_base64_content or (form.get("content") if normalized_source_type == ContentType.pdf_base64 else None),
            "metadata": metadata_dict,
        }
        try:
            upload_request = UploadRequest.model_validate(payload)
        except ValidationError as exc:
            detail = exc.errors()[0].get("msg", "Invalid form payload")
            raise HTTPException(422, detail) from exc

    source_type_value = upload_request.content_type.value if upload_request else source_type

    logger.info(f"[UPLOAD] New upload request | bot_id={bot_id[:8]}... | type={source_type_value} | client={client_ip}")
    logger.debug(f"[UPLOAD] Parsed metadata: {metadata_dict}")
    
    try:
        # Load documents based on content type
        logger.info(f"[UPLOAD] Loading documents from source (type={source_type_value})...")
        match upload_request.content_type:
            case ContentType.website:
                documents = await url_reader.load(upload_request.website_url, bot_id)
            case ContentType.pdf_url:
                documents = await _load_pdf_from_url(upload_request.pdf_url, bot_id)
            case ContentType.pdf_base64:
                documents = pdf_reader.load(upload_request.pdf_base64_content, bot_id)
            case ContentType.pdf_file:
                uploaded_pdf = pdf_file or form.get("file")
                if not uploaded_pdf:
                    raise HTTPException(422, "file is required for pdf_file type")
                logger.info(f"[UPLOAD] Reading PDF file: {uploaded_pdf.filename} ({uploaded_pdf.size if hasattr(uploaded_pdf, 'size') else 'unknown'} bytes)")
                # Read file content and encode as base64
                file_content = await uploaded_pdf.read()
                logger.info(f"[UPLOAD] PDF loaded: {len(file_content)} bytes")
                documents = pdf_reader.load_bytes(file_content, bot_id)
            case ContentType.text:
                documents = text_reader.load(upload_request.text_content, bot_id)
            case _:
                logger.error("invalid_content_type", content_type=source_type_value, bot_id=bot_id)
                raise HTTPException(400, f"Unsupported content type: {source_type_value}")
        
        if not documents:
            logger.warning("no_extractable_content", bot_id=bot_id, content_type=content_type)
            raise NoExtractableContentError("No extractable content found in source.")
        
        logger.info(f"[UPLOAD] Documents loaded: {len(documents)} document(s) extracted")
        
        # Process through ingestion pipeline
        logger.info(f"[UPLOAD] Starting ingestion pipeline...")
        result = await ingest_documents(bot_id=bot_id, documents=documents)
        
        if result.node_count == 0:
            logger.warning(f"[UPLOAD] No chunks created - content too short")
            raise NoExtractableContentError("Content too short to create meaningful chunks.")
        
        logger.info(f"[UPLOAD] Ingestion complete: {result.node_count} chunks, {result.token_count} tokens")
        
        # Create bot stats record
        logger.info(f"[UPLOAD] Creating bot record in database...")
        await create_bot_record(bot_id)
        
        logger.info(f"[UPLOAD] SUCCESS | bot_id={bot_id[:8]}... | chunks={result.node_count} | tokens={result.token_count}")
        
        return UploadResponse(
            bot_id=bot_id,
            chunks_created=result.node_count,
            tokens_ingested=result.token_count,
            source_type=source_type_value,
            message="Knowledge base ready. Use this bot_id to chat.",
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"[UPLOAD] FAILED | bot_id={bot_id[:8]}... | reason=validation_error | error={str(e)}")
        raise HTTPException(422, str(e)) from e
    except NoExtractableContentError as e:
        logger.warning(f"[UPLOAD] FAILED | bot_id={bot_id[:8]}... | reason=no_content | error={str(e)}")
        raise HTTPException(422, str(e))
    except IngestionError as e:
        logger.error(f"[UPLOAD] FAILED | bot_id={bot_id[:8]}... | reason=ingestion_error | error={str(e)}")
        raise HTTPException(500, f"Ingestion failed: {str(e)}")
    except Exception as e:
        logger.error(f"[UPLOAD] FAILED | bot_id={bot_id[:8]}... | reason=unexpected | error={str(e)}")
        raise HTTPException(500, f"Unexpected error: {str(e)}")
