"""Rule-based speak/skip policy; policy decisions never come from the model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta


@dataclass(frozen=True, slots=True)
class SpeakDecision:
    speak: bool
    reason: str


def _in_quiet_hours(now: datetime, quiet_hours: str | None) -> bool:
    if not quiet_hours:
        return False
    start_raw, end_raw = quiet_hours.split("-", 1)
    start, end = time.fromisoformat(start_raw), time.fromisoformat(end_raw)
    local_now = now.astimezone() if now.tzinfo else now
    current = local_now.timetz().replace(tzinfo=None)
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _is_fast_burst(rows: list[dict[str, object]]) -> bool:
    if len(rows) < 3:
        return False
    recent = rows[-3:]
    for row in recent:
        command = str(row["command"]).strip().split(maxsplit=1)[0].lower()
        if command not in {"cd", "ls", "dir", "pwd", "get-childitem"}:
            return False
    times = [datetime.fromisoformat(str(row["occurred_at"])) for row in recent]
    return (times[-1] - times[0]).total_seconds() <= 8


def _forced_reason(rows: list[dict[str, object]], now: datetime, event_count: int) -> str | None:
    if len(rows) >= 3:
        last_three = rows[-3:]
        if len({str(row["command"]) for row in last_three}) == 1 and all(
            int(row["exit_code"]) != 0 for row in last_three
        ):
            return "same command failed three times"
    if now.hour >= 23:
        return "late-night command"
    if len(rows) >= 2:
        previous = datetime.fromisoformat(str(rows[-2]["occurred_at"]))
        current = datetime.fromisoformat(str(rows[-1]["occurred_at"]))
        if current.date() != previous.date() and current - previous >= timedelta(hours=8):
            return "first command after a long gap"
    if event_count and event_count % 100 == 0:
        return "command milestone"
    if re.search(r"(?i)(?:rm\s+-rf|git\s+push\s+--force|drop\s+table|\bformat(?:\s|$))", str(rows[-1]["command"])):
        return "destructive command warning"
    if (now.month, now.day) in {(10, 31), (11, 1), (11, 2)}:
        return "seasonal haunting"
    if now.day == 13 and now.weekday() == 4:
        return "Friday the 13th"
    return None


def should_speak(
    rows: list[dict[str, object]],
    *,
    event_count: int,
    quiet_hours: str | None = None,
    hush_until: datetime | None = None,
) -> SpeakDecision:
    """Decide whether the current (last) stored event may receive a whisper."""
    if not rows:
        return SpeakDecision(False, "no command event")
    current = datetime.fromisoformat(str(rows[-1]["occurred_at"]))
    if current.tzinfo:
        current = current.astimezone()
    if hush_until and current < hush_until:
        return SpeakDecision(False, "temporary hush is active")
    if _in_quiet_hours(current, quiet_hours):
        return SpeakDecision(False, "quiet hours are active")
    forced = _forced_reason(rows, current, event_count)
    if _is_fast_burst(rows):
        return SpeakDecision(False, "fast repeated commands")
    recent_whispers = [row for row in rows[-4:] if row.get("whispered")]
    if recent_whispers:
        return SpeakDecision(False, "minimum four-command spacing")
    if forced:
        return SpeakDecision(True, forced)
    if event_count % 4 == 0:
        return SpeakDecision(True, "ordinary interval")
    return SpeakDecision(False, "ordinary interval not reached")
