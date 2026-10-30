"""Local configuration for Poltergeist."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime settings. Values are local and intentionally contain no API credentials."""

    model: str = DEFAULT_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    data_dir: Path = Path.home() / ".poltergeist"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "ghost.db"

    @classmethod
    def from_env(cls) -> Config:
        """Load supported settings from environment variables."""
        model = os.environ.get("POLTERGEIST_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        ollama_url = os.environ.get("POLTERGEIST_OLLAMA_URL", DEFAULT_OLLAMA_URL).strip()
        data_dir = Path(
            os.environ.get("POLTERGEIST_DATA_DIR", str(Path.home() / ".poltergeist"))
        ).expanduser()
        return cls(model=model, ollama_url=ollama_url.rstrip("/"), data_dir=data_dir)
