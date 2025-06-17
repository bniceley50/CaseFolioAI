import pytest, httpx, os
pytestmark=pytest.mark.asyncio
async def test_api_is_alive():
    base_url=os.getenv('API_BASE_URL','http://127.0.0.1:8000')
    async with httpx.AsyncClient() as client:
        response = await client.get(f'{base_url}/docs')
        assert response.status_code == 200