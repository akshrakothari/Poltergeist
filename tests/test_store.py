from datetime import datetime, timezone

from poltergeist.store import CommandEvent, EventStore


def test_store_redacts_before_persisting(tmp_path) -> None:
    store = EventStore(tmp_path / "ghost.db")
    store.record(
        CommandEvent(
            command="tool --token=secret123456",
            exit_code=0,
            duration_ms=12.5,
            cwd="C:/work/AQ.1234567890abcdefgh/demo",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    event = store.recent_events()[0]
    assert "secret123456" not in event.command
    assert "<REDACTED>" in event.command
    assert "AQ.1234567890abcdefgh" not in event.cwd


def test_facts_are_derived_from_sqlite_history(tmp_path) -> None:
    store = EventStore(tmp_path / "ghost.db")
    now = datetime.now(timezone.utc)
    for exit_code in (0, 1, 1):
        store.record(CommandEvent("git status", exit_code, 10, "C:/work/poltergeist", now))
    assert store.command_count() == 3
    assert store.facts_for("git status") == [
        "This exact command has appeared 3 times.",
        "It has failed 2 times.",
        "You most often ran it from poltergeist.",
    ]


def test_unknown_command_has_no_facts(tmp_path) -> None:
    assert EventStore(tmp_path / "ghost.db").facts_for("whoami") == []


def test_fact_limit_is_respected(tmp_path) -> None:
    store = EventStore(tmp_path / "ghost.db")
    store.record(
        CommandEvent("whoami", 1, 1, "/tmp", datetime.now(timezone.utc))
    )
    assert len(store.facts_for("whoami", limit=1)) == 1


def test_memory_facts_are_sql_summaries(tmp_path) -> None:
    store = EventStore(tmp_path / "ghost.db")
    now = datetime(2026, 10, 30, 22, 15, tzinfo=timezone.utc)
    store.record(CommandEvent("python app.py", 1, 25, "/work/haunted", now))
    facts = store.memory_facts()
    assert any("late-night stretch" in fact for fact in facts)
    assert any("Most-failed command" in fact for fact in facts)
    assert any("Oldest remembered folder" in fact for fact in facts)
    assert any("used only once" in fact for fact in facts)
