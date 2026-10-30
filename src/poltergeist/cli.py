"""Poltergeist command line interface."""

from __future__ import annotations

import asyncio
import base64
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt

from poltergeist.config import Config
from poltergeist.ollama import OllamaClient, OllamaError
from poltergeist.personas import available_personas, load_persona
from poltergeist.policy import should_speak
from poltergeist.redact import redact_command
from poltergeist.settings import UserSettings, hush_until as make_hush_until, load_settings, save_settings
from poltergeist.shells import install_powershell_hook, powershell_profile_path, uninstall_powershell_hook
from poltergeist.store import CommandEvent, EventStore
from poltergeist.whisper import (
    HauntingBrief,
    WhisperService,
    destructive_warning,
    offline_whisper,
    seasonal_whisper,
    valid_whisper,
)

app = typer.Typer(help="A read-only ghost for your terminal.", no_args_is_help=True)
console = Console()


def _state() -> tuple[Config, UserSettings, EventStore]:
    config = Config.from_env()
    return config, load_settings(config.data_dir / "config.json"), EventStore(config.database_path)


def _decode_b64(value: str) -> str:
    return base64.b64decode(value.encode("ascii"), validate=True).decode("utf-8")


def _write_pending(data_dir: Path, whisper: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    pending = data_dir / "pending.txt"
    content = whisper.replace("\r", " ").replace("\n", " ").strip()
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=data_dir, prefix="pending-", suffix=".tmp", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        os.replace(temporary, pending)
    finally:
        temporary.unlink(missing_ok=True)


def _short_story(facts: list[str]) -> str:
    """Bound the no-model story to the requested length."""
    return " ".join(" ".join(facts).split()[:150])


@app.command()
def init(persona: str | None = typer.Option(None, help="Persona to use.")) -> None:
    """Preview and install the PowerShell hook."""
    if not os.environ.get("PSModulePath"):
        console.print("PowerShell hook setup must be run from a PowerShell session.")
        raise typer.Abort()
    config = Config.from_env()
    settings_path = config.data_dir / "config.json"
    profile = powershell_profile_path()
    available = available_personas()
    if not available:
        raise typer.BadParameter("No persona files were found")
    chosen = persona or Prompt.ask("Choose a persona", choices=available, default="victorian")
    load_persona(chosen)
    console.print("[dim]  .-.\n (o o)\n  |=|[/]")
    console.print("[bold]Poltergeist setup preview[/]")
    console.print(f"Shell profile: {profile}")
    console.print(f"History database: {config.database_path}")
    console.print(f"Persona: {chosen}")
    console.print("The hook reads the last command, stores a redacted record asynchronously, and only prints text.")
    pending_file = config.data_dir / "pending.txt"
    hook_preview = powershell_hook(pending_file)
    console.print("Profile addition:\n[dim]" + "\n".join(hook_preview.splitlines()) + "[/]")
    if not typer.confirm("Install this PowerShell hook?", default=False):
        raise typer.Abort()
    install_powershell_hook(profile, pending_file)
    save_settings(settings_path, UserSettings(persona=chosen))
    console.print("[dim italic]~ A small specter has taken up residence in your prompt.[/]")

    client = OllamaClient(config.ollama_url, config.model)
    if asyncio.run(client.model_available()):
        console.print(f"Local model ready: {config.model}")
    else:
        console.print("Ollama or the selected model is unavailable. Offline whispers will still work.")
        if typer.confirm(f"Ask local Ollama to pull {config.model}?", default=False):
            try:
                asyncio.run(client.pull_model())
            except OllamaError as exc:
                console.print(f"[yellow]{exc}[/]")


@app.command(hidden=True)
def note(
    command_b64: str = typer.Option(..., "--command-b64"),
    cwd_b64: str = typer.Option(..., "--cwd-b64"),
    exit_code: int = typer.Option(..., "--exit-code"),
    duration_ms: float = typer.Option(0.0, "--duration-ms"),
    occurred_at: str = typer.Option("", "--occurred-at"),
) -> None:
    """Background hook endpoint: redact, persist, decide, and queue a whisper."""
    try:
        raw_command, cwd = _decode_b64(command_b64), _decode_b64(cwd_b64)
    except (ValueError, UnicodeDecodeError) as exc:
        raise typer.BadParameter("Invalid shell event payload") from exc
    if os.environ.get("POLTERGEIST_MEASURE_ONLY") == "1":
        return
    config, settings, store = _state()
    safe_cwd = redact_command(cwd)
    try:
        timestamp = datetime.fromisoformat(occurred_at) if occurred_at else datetime.now().astimezone()
    except ValueError:
        timestamp = datetime.now().astimezone()
    if timestamp.tzinfo is None:
        timestamp = timestamp.astimezone()
    event = CommandEvent(raw_command, exit_code, max(0.0, duration_ms), safe_cwd, timestamp)
    event_id = store.record(event)
    rows = store.recent_event_rows(limit=8, through=timestamp)
    hush_until_value = None
    if settings.hush_until:
        try:
            hush_until_value = datetime.fromisoformat(settings.hush_until)
            if hush_until_value.tzinfo is None:
                hush_until_value = hush_until_value.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    decision = should_speak(
        rows,
        event_count=store.command_count(as_of=timestamp),
        quiet_hours=settings.quiet_hours,
        hush_until=hush_until_value,
    )
    if not decision.speak:
        store.record_skip(event_id, decision.reason)
        return
    store.reserve_whisper(event_id)
    redacted = redact_command(raw_command)
    folder = Path(safe_cwd).name or safe_cwd
    now = event.occurred_at.astimezone()
    facts_list = store.facts_for(redacted, limit=3)
    if (now.month, now.day) == (10, 31):
        seasonal_fact = "Seasonal mode: Halloween, with a playful haunting."
    elif (now.month, now.day) in {(11, 1), (11, 2)}:
        seasonal_fact = "Seasonal mode: Día de los Muertos, with respectful remembrance."
    else:
        seasonal_fact = None
    facts = tuple((facts_list[:2] + [seasonal_fact]) if seasonal_fact else facts_list[:3])
    brief = HauntingBrief(redacted, exit_code, now.strftime("%H:%M"), folder, facts)
    try:
        persona = load_persona(settings.persona)
    except (OSError, ValueError):
        persona = load_persona("victorian")
    if decision.reason == "destructive command warning":
        whisper, fallback = destructive_warning(persona), True
    elif (now.month, now.day) == (10, 31):
        whisper, fallback = seasonal_whisper(persona, "Halloween"), True
    elif (now.month, now.day) in {(11, 1), (11, 2)}:
        whisper, fallback = seasonal_whisper(persona, "Día de los Muertos"), True
    else:
        try:
            service = WhisperService(OllamaClient(config.ollama_url, config.model), persona)
            whisper, fallback = asyncio.run(service.whisper(brief))
        except (OllamaError, ValueError):
            whisper, fallback = offline_whisper(persona, brief), True
    if not valid_whisper(whisper, brief.render()):
        whisper = persona.offline[0]
        fallback = True
    store.finalize_whisper(event_id, whisper, fallback)
    _write_pending(config.data_dir, whisper)


@app.command()
def mood() -> None:
    """Show persona, last whisper, and local counters."""
    config, settings, store = _state()
    stats = store.stats()
    console.print("[dim]  .-.")
    console.print(" (o o)")
    console.print("  |=|[/]")
    console.print(f"Persona: {settings.persona}")
    console.print(f"Commands remembered: {stats['commands']}")
    console.print(f"Whispers given: {stats['whispers']}")
    console.print(f"Whispers skipped for speed: {stats['skipped']}")
    console.print(f"Last whisper: {stats['last_whisper'] or 'none yet'}")
    console.print(f"Data: {config.data_dir}")


@app.command()
def hush(duration: str = typer.Argument("1h", help="Duration such as 30m, 2h, or 1d.")) -> None:
    """Pause whispers for a duration."""
    config, settings, _store = _state()
    try:
        settings.hush_until = make_hush_until(duration)
    except (ValueError, OverflowError) as exc:
        raise typer.BadParameter("Use a duration such as 30m, 2h, 1d, or seconds") from exc
    save_settings(config.data_dir / "config.json", settings)
    console.print(f"The ghost will be quiet until {settings.hush_until}.")


@app.command("quiet-hours")
def quiet_hours(value: str = typer.Argument(..., help="Local time range, for example 23:00-07:00.")) -> None:
    """Set the daily local quiet-hours window."""
    if not re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", value):
        raise typer.BadParameter("Use HH:MM-HH:MM, for example 23:00-07:00")
    start, end = value.split("-")
    try:
        datetime.strptime(start, "%H:%M")
        datetime.strptime(end, "%H:%M")
    except ValueError as exc:
        raise typer.BadParameter("Hours must be valid 24-hour times") from exc
    config, settings, _store = _state()
    settings.quiet_hours = value
    save_settings(config.data_dir / "config.json", settings)
    console.print(f"Quiet hours set to {value} local time.")


@app.command()
def remember() -> None:
    """Tell a short story from local SQL history."""
    config, settings, store = _state()
    facts = store.memory_facts()
    if not facts:
        console.print("[dim italic]~ There is no history to remember yet.[/]")
        return
    persona = load_persona(settings.persona)
    brief = "\n".join(f"- {fact}" for fact in facts)
    system = (
        f"You are {persona.name}. {persona.style} Tell a short ghost story using ONLY the facts "
        "below. Invent no numbers, dates, commands, or folder names. Maximum 150 words. No advice."
    )
    try:
        story = asyncio.run(OllamaClient(config.ollama_url, config.model).generate(brief, system=system))
    except (OllamaError, ValueError):
        story = _short_story(facts)
    if len(story.split()) > 150 or not valid_whisper(story, brief, max_words=150):
        story = _short_story(facts)
    console.print(f"[dim italic]~ {story}[/]")


@app.command()
def exorcise() -> None:
    """Remove the shell hook and all local Poltergeist data."""
    console.print("[dim]  .-.")
    console.print(" (o o)")
    console.print("  |=|[/]")
    if not typer.confirm("Remove the hook, settings, history database, and pending whisper?", default=False):
        raise typer.Abort()
    config = Config.from_env()
    profile = powershell_profile_path()
    uninstall_powershell_hook(profile)
    for path in (
        config.database_path,
        Path(str(config.database_path) + "-wal"),
        Path(str(config.database_path) + "-shm"),
        Path(str(config.database_path) + "-journal"),
        config.data_dir / "config.json",
        config.data_dir / "pending.txt",
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    for temporary in config.data_dir.glob("pending-*.tmp"):
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        config.data_dir.rmdir()
    except OSError:
        pass
    console.print("[dim italic]~ Farewell. I will leave no trace in this house.[/]")


if __name__ == "__main__":
    app()
