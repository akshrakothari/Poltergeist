from pathlib import Path

from poltergeist.settings import UserSettings, load_settings, save_settings


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    expected = UserSettings("gremlin", "23:00-07:00", "2026-10-30T00:00:00+00:00")
    save_settings(path, expected)
    assert load_settings(path) == expected


def test_bad_settings_fall_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("not json", encoding="utf-8")
    assert load_settings(path) == UserSettings()
