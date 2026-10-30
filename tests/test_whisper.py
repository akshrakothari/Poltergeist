from poltergeist.personas import load_persona
from poltergeist.whisper import (
    HauntingBrief,
    destructive_warning,
    offline_whisper,
    seasonal_whisper,
    valid_whisper,
)


def test_rejects_ungrounded_numbers() -> None:
    assert not valid_whisper("It failed 9 times.", "Command failed twice.")


def test_accepts_numbers_present_in_brief() -> None:
    assert valid_whisper("It failed 2 times.", "Failures: 2")


def test_enforces_word_limit_and_quotes() -> None:
    assert not valid_whisper("one two three four five six seven", "", max_words=5)
    assert not valid_whisper('"A whisper."', "")
    assert valid_whisper("The machine's quiet now.", "")


def test_rejects_emoji() -> None:
    assert not valid_whisper("The ghost is here 👻", "")


def test_offline_whisper_is_deterministic_and_bounded() -> None:
    persona = load_persona("gremlin")
    brief = HauntingBrief("git status", 0, "night", "attic", ())
    assert offline_whisper(persona, brief) == offline_whisper(persona, brief)
    assert len(offline_whisper(persona, brief).split()) <= 30
    assert valid_whisper(offline_whisper(persona, brief), brief.render())


def test_destructive_warning_is_gentle_and_short() -> None:
    for persona_name in ("victorian", "ofrenda", "cobol", "gremlin"):
        warning = destructive_warning(load_persona(persona_name))
        assert len(warning.split()) <= 30
        assert "?" not in warning


def test_seasonal_lines_are_available_offline_for_each_persona() -> None:
    for persona_name in ("victorian", "ofrenda", "cobol", "gremlin"):
        persona = load_persona(persona_name)
        for mode in ("Halloween", "Día de los Muertos"):
            line = seasonal_whisper(persona, mode)
            assert len(line.split()) <= 30
            assert valid_whisper(line, "")
