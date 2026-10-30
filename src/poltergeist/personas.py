"""Load small, user-editable persona files."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

PERSONA_DIR = Path(__file__).with_name("personas")


@dataclass(frozen=True, slots=True)
class Persona:
    name: str
    style: str
    examples: tuple[str, ...]
    offline: tuple[str, ...]


def load_persona(name: str, directory: Path = PERSONA_DIR) -> Persona:
    """Load a persona by slug, rejecting paths outside the persona directory."""
    if not name or Path(name).name != name:
        raise ValueError("Persona name must be a simple slug")
    path = directory / f"{name}.toml"
    with path.open("rb") as stream:
        raw = tomllib.load(stream)
    examples = tuple(str(value) for value in raw.get("examples", []))
    offline = tuple(str(value) for value in raw.get("offline", []))
    if not raw.get("name") or not raw.get("style") or len(examples) < 10 or len(offline) < 40:
        raise ValueError(f"Persona {name!r} must include a name, style, 10 examples, and 40 whispers")
    return Persona(str(raw["name"]), str(raw["style"]), examples, offline)


def available_personas(directory: Path = PERSONA_DIR) -> list[str]:
    return sorted(path.stem for path in directory.glob("*.toml"))
