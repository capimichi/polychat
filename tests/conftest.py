import sys
import types

import pytest

# Provide light stubs for optional heavy dependencies so imports succeed in test envs
if "camoufox" not in sys.modules:
    camoufox_module = types.ModuleType("camoufox")
    async_api_module = types.ModuleType("camoufox.async_api")

    class _AsyncCamoufox:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def new_context(self, **kwargs):
            raise RuntimeError("AsyncCamoufox stub: not implemented")

    async_api_module.AsyncCamoufox = _AsyncCamoufox
    camoufox_module.async_api = async_api_module
    sys.modules["camoufox"] = camoufox_module
    sys.modules["camoufox.async_api"] = async_api_module

if "browserforge" not in sys.modules:
    browserforge_module = types.ModuleType("browserforge")
    fingerprints_module = types.ModuleType("browserforge.fingerprints")

    class _Screen:
        def __init__(self, *_, **__):
            pass

    fingerprints_module.Screen = _Screen
    browserforge_module.fingerprints = fingerprints_module
    sys.modules["browserforge"] = browserforge_module
    sys.modules["browserforge.fingerprints"] = fingerprints_module

from polychat.service.chat_service import ChatService
from tests.fakes.fake_perplexity_client import FakePerplexityClient


@pytest.fixture
def fake_perplexity_client():
    return FakePerplexityClient()


@pytest.fixture
def chat_service(fake_perplexity_client):
    return ChatService(fake_perplexity_client)
