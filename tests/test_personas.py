from pathlib import Path

import pytest

from poltergeist.personas import available_personas, load_persona
from poltergeist.whisper import HauntingBrief, valid_whisper


def test_all_builtin_personas_have_offline_pools() -> None:
    assert set(available_personas()) == {"victorian", "ofrenda", "cobol", "gremlin"}
    for name in available_personas():
        persona = load_persona(name)
        assert len(persona.examples) >= 10
        assert len(persona.offline) >= 40
        brief = HauntingBrief("git status", 0, "night", "attic", ())
        assert all(valid_whisper(line, brief.render()) for line in persona.offline)


def test_persona_slug_cannot_escape_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_persona("../outside", tmp_path)


def test_incomplete_persona_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.toml").write_text(
        'name="Bad"\nstyle="Quiet"\nexamples=["only one"]\n', encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_persona("bad", tmp_path)
