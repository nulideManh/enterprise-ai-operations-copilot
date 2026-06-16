import pytest

@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Enterprise AI Operations Copilot"}

@pytest.mark.asyncio
async def test_llm_status_endpoint(async_client):
    response = await async_client.get("/api/llm/status")
    assert response.status_code == 200
    data = response.json()
    assert "provider" in data
    assert "openai_configured" in data
    assert "local_available" in data
