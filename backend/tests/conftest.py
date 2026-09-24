import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from p2_fakes import CatalogFakeProvider
from realtime_fakes import FakeClock, RealtimeBundle

FIXED_NOW = "2026-09-08T10:00:00Z"

# Importing app.main creates the ASGI app immediately. Keep that import
# hermetic under pytest while preserving the production Settings model
# default; tests that specifically exercise dotenv pass `_env_file` explicitly.
_settings_init = Settings.__init__


def _settings_init_without_dotenv(self, *args, **kwargs):
    kwargs.setdefault("_env_file", None)
    _settings_init(self, *args, **kwargs)


Settings.__init__ = _settings_init_without_dotenv


@pytest.fixture()
async def client() -> AsyncClient:
    from app.main import create_app

    app = create_app(
        Settings(_env_file=None, fixed_now=FIXED_NOW),
        realtime=RealtimeBundle(FakeClock()),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture()
async def catalog_provider() -> CatalogFakeProvider:
    provider = CatalogFakeProvider()
    await provider.build()
    return provider
