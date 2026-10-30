from datetime import datetime, timezone

from poltergeist.policy import should_speak


def rows(commands, *, start_hour=12, whispered_at=None, interval=10):
    result = []
    for index, command in enumerate(commands, start=1):
        result.append({
            "id": index,
            "command": command,
            "exit_code": 1 if command.endswith(" fail") else 0,
            "duration_ms": 1.0,
            "cwd": "/tmp",
            "occurred_at": datetime(2026, 10, 20, start_hour, 0, index * interval, tzinfo=timezone.utc).isoformat(),
            "whispered": index == whispered_at,
        })
    return result


def test_ordinary_schedule_is_no_more_than_every_four_commands():
    decision = should_speak(rows(["git status"] * 4), event_count=4)
    assert decision.speak


def test_recent_whisper_enforces_four_command_gap():
    decision = should_speak(rows(["git status"] * 4, whispered_at=2), event_count=4)
    assert not decision.speak


def test_quiet_hours_override_forced_event():
    events = rows(["rm -rf /"], start_hour=23)
    assert not should_speak(events, event_count=1, quiet_hours="23:00-07:00").speak


def test_repeated_navigation_burst_is_suppressed():
    events = rows(["cd one", "ls", "cd two"], interval=1)
    assert not should_speak(events, event_count=3).speak


def test_three_failures_force_a_whisper():
    events = rows(["build fail"] * 3)
    decision = should_speak(events, event_count=3)
    assert decision.speak
    assert "failed three times" in decision.reason


def test_hush_suppresses_forced_whisper():
    events = rows(["rm -rf /"], start_hour=23)
    hush = datetime(2026, 10, 21, tzinfo=timezone.utc)
    assert not should_speak(events, event_count=1, hush_until=hush).speak
