"""SQLite-backed local command event storage and history facts."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from poltergeist.redact import redact_command


@dataclass(frozen=True, slots=True)
class CommandEvent:
    command: str
    exit_code: int
    duration_ms: float
    cwd: str
    occurred_at: datetime


class EventStore:
    """Store only redacted command events in a local SQLite database."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS command_events (
                    id INTEGER PRIMARY KEY,
                    command TEXT NOT NULL,
                    exit_code INTEGER NOT NULL,
                    duration_ms REAL NOT NULL CHECK(duration_ms >= 0),
                    cwd TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_command_time "
                "ON command_events(command, occurred_at)"
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS whispers (
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL REFERENCES command_events(id),
                    text TEXT NOT NULL,
                    used_fallback INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS skipped_whispers (
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL REFERENCES command_events(id),
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )

    def record(self, event: CommandEvent) -> int:
        """Persist a command event after redaction, returning its row ID."""
        safe_command = redact_command(event.command)
        safe_cwd = redact_command(event.cwd)
        timestamp = event.occurred_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO command_events
                   (command, exit_code, duration_ms, cwd, occurred_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    safe_command,
                    int(event.exit_code),
                    max(0.0, float(event.duration_ms)),
                    safe_cwd,
                    timestamp.astimezone(timezone.utc).isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def command_count(self, *, as_of: datetime | None = None) -> int:
        with self._connect() as connection:
            if as_of is None:
                row = connection.execute("SELECT COUNT(*) AS count FROM command_events").fetchone()
            else:
                timestamp = as_of.astimezone(timezone.utc).isoformat()
                row = connection.execute(
                    "SELECT COUNT(*) AS count FROM command_events WHERE occurred_at <= ?",
                    (timestamp,),
                ).fetchone()
            return int(row["count"])

    def facts_for(self, command: str, *, limit: int = 3) -> list[str]:
        """Return compact, deterministic facts for a redacted command."""
        safe_command = redact_command(command)
        facts: list[str] = []
        with self._connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) AS failures
                   FROM command_events WHERE command = ?""",
                (safe_command,),
            ).fetchone()
            total = int(row["total"])
            failures = int(row["failures"] or 0)
            if total:
                facts.append(f"This exact command has appeared {total} times.")
                if failures:
                    facts.append(f"It has failed {failures} times.")
            row = connection.execute(
                """SELECT cwd, COUNT(*) AS total FROM command_events
                   WHERE command = ? GROUP BY cwd ORDER BY total DESC, cwd LIMIT 1""",
                (safe_command,),
            ).fetchone()
            if row is not None:
                folder = Path(str(row["cwd"])).name or str(row["cwd"])
                facts.append(f"You most often ran it from {folder}.")
        return facts[: max(0, limit)]

    def recent_events(self, *, limit: int = 20) -> list[CommandEvent]:
        """Return recent events in chronological order, with already-redacted commands."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT command, exit_code, duration_ms, cwd, occurred_at
                   FROM command_events ORDER BY id DESC LIMIT ?""",
                (max(0, limit),),
            ).fetchall()
        events = [
            CommandEvent(
                command=str(row["command"]),
                exit_code=int(row["exit_code"]),
                duration_ms=float(row["duration_ms"]),
                cwd=str(row["cwd"]),
                occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
            )
            for row in rows
        ]
        return list(reversed(events))

    def recent_event_rows(
        self, *, limit: int = 20, through: datetime | None = None
    ) -> list[dict[str, object]]:
        """Return event rows including IDs for policy decisions."""
        with self._connect() as connection:
            query = """SELECT e.id, e.command, e.exit_code, e.duration_ms, e.cwd, e.occurred_at,
                              EXISTS(SELECT 1 FROM whispers w WHERE w.event_id = e.id) AS whispered
                       FROM command_events e"""
            params: list[object] = []
            if through is not None:
                query += " WHERE e.occurred_at <= ?"
                params.append(through.astimezone(timezone.utc).isoformat())
            query += " ORDER BY e.occurred_at DESC, e.id DESC LIMIT ?"
            params.append(max(0, limit))
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in reversed(rows)]

    def reserve_whisper(self, event_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO whispers(event_id, text, used_fallback, created_at) VALUES (?, ?, ?, ?)",
                (event_id, "", 0, datetime.now(timezone.utc).isoformat()),
            )

    def finalize_whisper(self, event_id: int, text: str, used_fallback: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE whispers SET text = ?, used_fallback = ? WHERE event_id = ?",
                (text, int(used_fallback), event_id),
            )

    def record_skip(self, event_id: int, reason: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO skipped_whispers(event_id, reason, created_at) VALUES (?, ?, ?)",
                (event_id, reason, datetime.now(timezone.utc).isoformat()),
            )

    def stats(self) -> dict[str, int | str | None]:
        with self._connect() as connection:
            events = int(connection.execute("SELECT COUNT(*) FROM command_events").fetchone()[0])
            whispers = int(connection.execute("SELECT COUNT(*) FROM whispers").fetchone()[0])
            skipped = int(connection.execute(
                "SELECT COUNT(*) FROM skipped_whispers WHERE reason = 'fast repeated commands'"
            ).fetchone()[0])
            last = connection.execute(
                "SELECT COALESCE(NULLIF(text, ''), '(whisper pending)') "
                "FROM whispers ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {"commands": events, "whispers": whispers, "skipped": skipped,
                "last_whisper": str(last[0]) if last else None}

    def memory_facts(self) -> list[str]:
        """Summarize long-running history using SQL aggregates, never raw command text."""
        facts: list[str] = []
        with self._connect() as connection:
            row = connection.execute(
                """SELECT CASE WHEN CAST(substr(occurred_at, 12, 2) AS INTEGER) < 5
                               THEN date(occurred_at, '-1 day')
                               ELSE substr(occurred_at, 1, 10) END AS night, COUNT(*) AS total
                   FROM command_events WHERE CAST(substr(occurred_at, 12, 2) AS INTEGER) >= 22
                      OR CAST(substr(occurred_at, 12, 2) AS INTEGER) < 5
                   GROUP BY night ORDER BY total DESC, night ASC LIMIT 1"""
            ).fetchone()
            if row:
                facts.append(f"Your busiest late-night stretch began {row['night']} ({row['total']} commands).")
            row = connection.execute(
                """SELECT command, COUNT(*) AS failures FROM command_events
                   WHERE exit_code != 0 GROUP BY command ORDER BY failures DESC, command LIMIT 1"""
            ).fetchone()
            if row:
                facts.append(f"Most-failed command: {row['command']} ({row['failures']} failures).")
            row = connection.execute(
                """SELECT cwd, MIN(occurred_at) AS first_seen FROM command_events
                   GROUP BY cwd ORDER BY first_seen ASC LIMIT 1"""
            ).fetchone()
            if row:
                folder = Path(str(row["cwd"])).name or str(row["cwd"])
                facts.append(f"Oldest remembered folder: {folder}, first visited {str(row['first_seen'])[:10]}.")
            row = connection.execute(
                """SELECT command FROM command_events GROUP BY command HAVING COUNT(*) = 1
                   ORDER BY MIN(id) LIMIT 1"""
            ).fetchone()
            if row:
                facts.append(f"A command you have used only once: {row['command']}.")
        return facts
