"""Small local settings file; secrets are deliberately not supported here."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(slots=True)
class UserSettings:
    persona: str = "victorian"
    quiet_hours: str | None = None
    hush_until: str | None = None


def load_settings(path: Path) -> UserSettings:
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            return UserSettings()
        persona = values.get("persona", "victorian")
        quiet_hours = values.get("quiet_hours")
        hush_value = values.get("hush_until")
        return UserSettings(
            persona=persona if isinstance(persona, str) and persona else "victorian",
            quiet_hours=quiet_hours if isinstance(quiet_hours, str) else None,
            hush_until=hush_value if isinstance(hush_value, str) else None,
        )
    except FileNotFoundError:
        return UserSettings()
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return UserSettings()


def save_settings(path: Path, settings: UserSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    os.replace(temporary, path)


def parse_duration(value: str) -> timedelta:
    """Parse a small duration such as 30m, 2h, or 1d."""
    raw = value.strip().lower()
    if raw.endswith("m"):
        return timedelta(minutes=float(raw[:-1]))
    if raw.endswith("h"):
        return timedelta(hours=float(raw[:-1]))
    if raw.endswith("d"):
        return timedelta(days=float(raw[:-1]))
    return timedelta(seconds=float(raw))


def hush_until(value: str, *, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return (current + parse_duration(value)).astimezone(timezone.utc).isoformat()
