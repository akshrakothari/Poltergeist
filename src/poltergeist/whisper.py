"""Grounded whisper generation and offline fallback."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from poltergeist.ollama import OllamaClient, OllamaError
from poltergeist.personas import Persona

_DIGITS = re.compile(r"\b\d+\b")
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_WORDS = re.compile(r"\b(?:" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)
_DESTRUCTIVE_WARNINGS = {
    "Victorian Ghost": "A forceful command can leave lasting silences; I hope its effects are intended.",
    "Ofrenda": "This command may reshape old work; the ghost pauses beside it with care.",
    "The COBOL Ghost": "This operation may alter records beyond recovery; I have entered a quiet warning.",
    "Gremlin": "That command has sharp edges; even this gremlin is backing away.",
}
_SEASONAL_WHISPERS = {
    "Halloween": {
        "Victorian Ghost": "The veil feels thin tonight; even the cursor keeps watch.",
        "Ofrenda": "Tonight we remember with care and leave a gentle light for those who came before.",
        "The COBOL Ghost": "The batch window is haunted; even my records are wearing shadows.",
        "Gremlin": "The terminal has put on a sheet. It says the build is spooky-ready.",
    },
    "Día de los Muertos": {
        "Victorian Ghost": "Old paths are warmly remembered in this quiet hour.",
        "Ofrenda": "We remember those who came before with tenderness and care.",
        "The COBOL Ghost": "The records of those who came before remain in the archive.",
        "Gremlin": "The archive is full of ghosts; they brought snacks, respectfully.",
    },
}


@dataclass(frozen=True, slots=True)
class HauntingBrief:
    command: str
    exit_code: int
    time_of_day: str
    folder: str
    facts: tuple[str, ...]

    def render(self) -> str:
        facts = "\n".join(f"- {fact}" for fact in self.facts) or "- No history facts available."
        return (
            f"Command: {self.command}\nExit code: {self.exit_code}\n"
            f"Time of day: {self.time_of_day}\nFolder: {self.folder}\nFacts:\n{facts}"
        )


def _number_values(text: str) -> set[int]:
    values = {int(item) for item in _DIGITS.findall(text)}
    values.update(_NUMBER_WORDS[word.lower()] for word in _WORDS.findall(text))
    return values


def valid_whisper(text: str, brief: str, *, max_words: int = 30) -> bool:
    """Reject empty, quoted, emoji-like, too-long, or numerically ungrounded whispers."""
    candidate = text.strip()
    if not candidate or len(candidate.split()) > max_words:
        return False
    if "\n" in candidate or any(mark in candidate for mark in ('"', "“", "”", "‘", "’", "`")):
        return False
    if any(unicodedata.category(char) in {"So", "Sk"} for char in candidate):
        return False
    return _number_values(candidate) <= _number_values(brief)


def offline_whisper(persona: Persona, brief: HauntingBrief) -> str:
    """Choose a deterministic, hand-written whisper without model access."""
    seed = f"{brief.command}|{brief.exit_code}|{brief.time_of_day}|{brief.folder}"
    index = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(persona.offline)
    return persona.offline[index]


def destructive_warning(persona: Persona) -> str:
    """Return a gentle, non-blocking warning for destructive commands."""
    return _DESTRUCTIVE_WARNINGS.get(persona.name, _DESTRUCTIVE_WARNINGS["Victorian Ghost"])


def seasonal_whisper(persona: Persona, mode: str) -> str:
    """Return a short, authored seasonal line without requiring model access."""
    lines = _SEASONAL_WHISPERS.get(mode, _SEASONAL_WHISPERS["Halloween"])
    return lines.get(persona.name, lines["Victorian Ghost"])


class WhisperService:
    def __init__(self, client: OllamaClient, persona: Persona) -> None:
        self.client = client
        self.persona = persona

    async def whisper(self, brief: HauntingBrief) -> tuple[str, bool]:
        """Return (whisper, used_fallback); all prompts contain redacted brief text only."""
        rendered = brief.render()
        system = (
            f"You are {self.persona.name}. {self.persona.style} Use ONLY facts in the brief; "
            "invent no numbers, dates, folder names, or personal details. Write one whisper, "
            "30 words maximum, with no emoji, quotation marks, or advice."
        )
        for _attempt in range(2):
            try:
                answer = await self.client.generate(rendered, system=system)
            except (OllamaError, ValueError):
                break
            if valid_whisper(answer, rendered):
                return answer.strip(), False
        return offline_whisper(self.persona, brief), True
