from pathlib import Path

from poltergeist.shells import HOOK_BEGIN, HOOK_END, install_powershell_hook, uninstall_powershell_hook


def test_profile_install_backs_up_and_uninstall_preserves_other_content(tmp_path: Path) -> None:
    profile = tmp_path / "profile.ps1"
    profile.write_text("function prompt { 'ready> ' }\n", encoding="utf-8")
    install_powershell_hook(profile)
    backup = profile.with_suffix(".ps1.poltergeist.bak")
    assert backup.read_text(encoding="utf-8") == "function prompt { 'ready> ' }\n"
    installed = profile.read_text(encoding="utf-8")
    assert HOOK_BEGIN in installed and HOOK_END in installed
    assert uninstall_powershell_hook(profile)
    cleaned = profile.read_text(encoding="utf-8")
    assert "function prompt" in cleaned
    assert HOOK_BEGIN not in cleaned


def test_install_is_idempotent(tmp_path: Path) -> None:
    profile = tmp_path / "profile.ps1"
    install_powershell_hook(profile)
    original = profile.read_text(encoding="utf-8")
    install_powershell_hook(profile)
    assert profile.read_text(encoding="utf-8") == original


def test_uninstall_does_not_touch_unrelated_profile(tmp_path: Path) -> None:
    profile = tmp_path / "profile.ps1"
    profile.write_text("Write-Output ready\n", encoding="utf-8")
    assert not uninstall_powershell_hook(profile)
    assert profile.read_text(encoding="utf-8") == "Write-Output ready\n"
