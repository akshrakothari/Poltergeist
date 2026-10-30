"""Small local-only client for Ollama's generate endpoint."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

import httpx

from poltergeist.config import DEFAULT_MODEL, DEFAULT_OLLAMA_URL


class OllamaError(RuntimeError):
    """Raised when local Ollama is unavailable or returns an invalid response."""


def _validate_local_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Ollama URL must use HTTP on the local machine")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Ollama URL cannot contain credentials, query, or fragment")
    return url.rstrip("/")


class OllamaClient:
    """Generate text only through a loopback Ollama server."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 4.0,
    ) -> None:
        self.base_url = _validate_local_url(base_url)
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def generate(self, prompt: str, *, system: str = "") -> str:
        """Ask Ollama for a response; callers should run this outside the shell prompt path."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.9, "num_predict": 96},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
        except (httpx.HTTPError, TimeoutError) as exc:
            raise OllamaError("Local Ollama could not answer") from exc
        try:
            text = response.json()["response"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError("Local Ollama returned an invalid response") from exc
        if not isinstance(text, str):
            raise OllamaError("Local Ollama returned an invalid response")
        return text.strip()

    async def model_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
            return any(
                item.get("name") == self.model or item.get("name", "").startswith(self.model + ":")
                for item in response.json().get("models", [])
            )
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return False

    async def pull_model(self) -> None:
        """Request a model pull from the local Ollama server (no direct remote request here)."""
        try:
            async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/pull", json={"name": self.model, "stream": True}
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                status = json.loads(line).get("status")
                            except (json.JSONDecodeError, AttributeError):
                                status = None
                            if status:
                                print(status)
        except httpx.HTTPError as exc:
            raise OllamaError("Could not pull the model through local Ollama") from exc
