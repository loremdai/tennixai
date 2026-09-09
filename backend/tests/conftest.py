import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from p2_fakes import CatalogFakeProvider

FIXED_NOW = "2026-09-08T10:00:00Z"


@pytest.fixture()
async def client() -> AsyncClient:
    app = create_app(Settings(_env_file=None, fixed_now=FIXED_NOW))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture()
async def catalog_provider() -> CatalogFakeProvider:
    provider = CatalogFakeProvider()
    await provider.build()
    return provider
