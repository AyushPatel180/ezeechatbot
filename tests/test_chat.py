"""Tests for chat endpoint."""
import pytest


class TestChatStreaming:
    """Test chat streaming functionality."""
    
    async def test_chat_streaming_success(self, client):
        """Test successful chat returns streaming response."""
        # First upload a knowledge base
        upload_resp = await client.post("/upload", json={
            "content_type": "text",
            "content": "The refund policy is 30 days. Customers must provide receipt."
        })
        
        if upload_resp.status_code != 200:
            pytest.skip("Upload failed, skipping chat test")
        
        bot_id = upload_resp.json()["bot_id"]
        
        # Chat with the bot
        response = await client.post("/chat", json={
            "bot_id": bot_id,
            "user_message": "What is the refund policy?"
        })
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"
    
    async def test_chat_invalid_bot_id(self, client):
        """Test chat with non-existent bot_id returns 404."""
        response = await client.post("/chat", json={
            "bot_id": "invalid-bot-id-12345",
            "user_message": "Hello?"
        })
        
        assert response.status_code == 404


class TestChatHallucinationGuard:
    """Test hallucination prevention."""
    
    async def test_chat_off_topic_question(self, client):
        """Test off-topic question returns fallback, not hallucination."""
        # Upload limited content
        upload_resp = await client.post("/upload", json={
            "content_type": "text",
            "content": "We sell shoes. Our shoes are high quality."
        })
        
        if upload_resp.status_code != 200:
            pytest.skip("Upload failed, skipping test")
        
        bot_id = upload_resp.json()["bot_id"]
        
        # Ask off-topic question
        response = await client.post("/chat", json={
            "bot_id": bot_id,
            "user_message": "What is the capital of France?"
        })
        
        assert response.status_code == 200
        # The response should indicate it's unanswerable
        content = response.content.decode()
        assert "unanswerable" in content.lower() or "couldn't find" in content.lower()


class TestChatValidation:
    """Test chat input validation."""
    
    async def test_chat_missing_message(self, client):
        """Test missing user_message returns error."""
        response = await client.post("/chat", json={
            "bot_id": "some-bot-id",
        })
        
        assert response.status_code == 422
    
    async def test_chat_empty_message(self, client):
        """Test empty user_message returns error."""
        response = await client.post("/chat", json={
            "bot_id": "some-bot-id",
            "user_message": ""
        })
        
        assert response.status_code == 422
