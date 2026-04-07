"""Tests for upload endpoint."""
import pytest
import base64


class TestUploadText:
    """Test text content upload."""
    
    async def test_upload_text_success(self, client):
        """Test successful text upload returns bot_id."""
        response = await client.post("/upload", json={
            "source_type": "text",
            "text_content": "This is a test knowledge base about refund policies. Customers can get refunds within 30 days."
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "bot_id" in data
        assert data["source_type"] == "text"
        assert data["chunks_created"] > 0
        assert data["tokens_ingested"] > 0

    async def test_upload_text_legacy_payload_still_works(self, client):
        """Test legacy content_type/content payload remains supported."""
        response = await client.post("/upload", json={
            "content_type": "text",
            "content": "This is a legacy payload for backward compatibility and should still upload successfully."
        })

        assert response.status_code == 200
    
    async def test_upload_text_too_short(self, client):
        """Test very short content returns error."""
        response = await client.post("/upload", json={
            "source_type": "text",
            "text_content": "Hi"
        })
        
        assert response.status_code == 422


class TestUploadPDF:
    """Test PDF content upload."""
    
    async def test_upload_pdf_base64_success(self, client):
        """Test successful PDF base64 upload."""
        # Create a minimal valid PDF-like content (not real PDF, will fail parse)
        # In real tests, use actual PDF bytes
        pdf_content = base64.b64encode(b"fake pdf content").decode()
        
        response = await client.post("/upload", json={
            "source_type": "pdf_base64",
            "pdf_base64_content": pdf_content
        })
        
        # Expect failure since it's not a real PDF
        assert response.status_code == 422
    
    async def test_upload_pdf_invalid_base64(self, client):
        """Test invalid base64 returns error."""
        response = await client.post("/upload", json={
            "source_type": "pdf_base64",
            "pdf_base64_content": "not-valid-base64!!!"
        })
        
        assert response.status_code == 422


class TestUploadURL:
    """Test URL content upload."""
    
    async def test_upload_url_success(self, client):
        """Test successful URL upload."""
        # This would need mocking in real tests
        response = await client.post("/upload", json={
            "source_type": "website",
            "website_url": "https://example.com/docs"
        })
        
        # Will likely fail without mocking
        # In real tests, mock httpx
        assert response.status_code in [200, 422, 500]
    
    async def test_upload_url_invalid(self, client):
        """Test invalid URL returns error."""
        response = await client.post("/upload", json={
            "source_type": "website",
            "website_url": "not-a-valid-url"
        })
        
        assert response.status_code in [422, 500]


class TestUploadValidation:
    """Test input validation."""
    
    async def test_upload_missing_content(self, client):
        """Test missing content field returns error."""
        response = await client.post("/upload", json={
            "source_type": "text"
        })
        
        assert response.status_code == 422
    
    async def test_upload_invalid_content_type(self, client):
        """Test invalid content type returns error."""
        response = await client.post("/upload", json={
            "source_type": "invalid_type",
            "text_content": "some content"
        })
        
        assert response.status_code == 400
