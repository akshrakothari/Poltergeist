import asyncio

import pytest

from poltergeist.ollama import OllamaClient


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://192.168.1.2:11434",
        "http://example.test:11434",
        "http://user:pass@127.0.0.1:11434",
    ],
)
def test_rejects_non_loopback_or_credentialed_urls(url: str) -> None:
    with pytest.raises(ValueError):
        OllamaClient(base_url=url)


@pytest.mark.parametrize("url", ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"])
def test_accepts_loopback_ollama_urls(url: str) -> None:
    assert OllamaClient(base_url=url).base_url == url


def test_generate_sends_requests_only_to_the_local_ollama_endpoint(monkeypatch) -> None:
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "A quiet little answer."}

    class FakeClient:
        def __init__(self, *, timeout, trust_env):
            assert trust_env is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            calls.append(url)
            return Response()

    monkeypatch.setattr("poltergeist.ollama.httpx.AsyncClient", FakeClient)
    answer = asyncio.run(OllamaClient().generate("hello"))
    assert answer == "A quiet little answer."
    assert calls == ["http://127.0.0.1:11434/api/generate"]
