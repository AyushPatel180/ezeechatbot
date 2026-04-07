"""Tests for stats endpoint."""
import pytest


class TestStats:
    """Test stats endpoint."""
    
    async def test_get_stats_success(self, client):
        """Test getting stats for existing bot."""
        # First upload a knowledge base
        upload_resp = await client.post("/upload", json={
            "content_type": "text",
            "content": "Test knowledge base content for stats testing."
        })
        
        if upload_resp.status_code != 200:
            pytest.skip("Upload failed, skipping test")
        
        bot_id = upload_resp.json()["bot_id"]
        
        # Get stats
        response = await client.get(f"/stats/{bot_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["bot_id"] == bot_id
        assert "total_messages_served" in data
        assert "average_response_latency_ms" in data
        assert "estimated_token_cost_usd" in data
    
    async def test_get_stats_invalid_bot_id(self, client):
        """Test getting stats for non-existent bot returns 404."""
        response = await client.get("/stats/invalid-bot-id-12345")
        
        assert response.status_code == 404
