import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from py_harness.ollama_client import OllamaClient

@pytest.mark.asyncio
async def test_ollama_chat():
    client = OllamaClient(base_url="http://localhost:11434")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "gemma4:12b",
            "message": {"role": "assistant", "content": "Hello!"},
            "done": True
        }
        mock_post.return_value = mock_response
        
        response = await client.chat(model="gemma4:12b", messages=[{"role": "user", "content": "Hi"}])
        assert response["message"]["content"] == "Hello!"
