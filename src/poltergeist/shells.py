"""PowerShell profile hook installation and removal."""

from __future__ import annotations

import shutil
from pathlib import Path

HOOK_BEGIN = "# >>> Poltergeist hook >>>"
HOOK_END = "# <<< Poltergeist hook <<<"


def powershell_profile_path(home: Path | None = None) -> Path:
    root = home or Path.home()
    documents = root / "Documents"
    core = documents / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
    windows = documents / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
    if windows.parent.exists() and not core.parent.exists():
        return windows
    return core


def powershell_hook(pending_file: Path | None = None) -> str:
    pending_literal = str(pending_file or (Path.home() / ".poltergeist" / "pending.txt"))
    pending_literal = pending_literal.replace("'", "''")
    return f'''{HOOK_BEGIN}
$global:PoltergeistOriginalPrompt = (Get-Command prompt -CommandType Function).ScriptBlock
function global:prompt {{
    $lastSuccess = $?
    $lastNativeExit = $global:LASTEXITCODE
    $historyItem = Get-History -Count 1 | Select-Object -First 1
    if ($historyItem -and $lastSuccess -and $historyItem.CommandLine -match '^\\s*ghost(?:\\.exe)?\\s+exorcise(?:\\s|$)') {{
        $originalPrompt = $global:PoltergeistOriginalPrompt
        Set-Item -Path Function:\\global:prompt -Value $originalPrompt -Force
        Remove-Variable -Name PoltergeistOriginalPrompt -Scope Global -ErrorAction SilentlyContinue
        & $originalPrompt
        return
    }}
    $pending = '{pending_literal}'
    if (Test-Path -LiteralPath $pending) {{
        $claimed = "$pending.$([Guid]::NewGuid().ToString('N')).read"
        try {{
            $null = Move-Item -LiteralPath $pending -Destination $claimed -ErrorAction Stop
            $whisper = [System.IO.File]::ReadAllText($claimed, [System.Text.Encoding]::UTF8).Trim()
            Remove-Item -LiteralPath $claimed -Force -ErrorAction SilentlyContinue
            if ($whisper) {{
                if ([string]::IsNullOrEmpty($env:NO_COLOR)) {{ Write-Host ("~ " + $whisper) -ForegroundColor DarkGray }}
                else {{ Write-Host ("~ " + $whisper) }}
            }}
        }} catch {{ }}
    }}
    if ($historyItem) {{
        $exitCode = if ($lastSuccess) {{ 0 }} elseif ($null -ne $lastNativeExit -and $lastNativeExit -ne 0) {{ $lastNativeExit }} else {{ 1 }}
        $duration = 0
        if ($historyItem.StartExecutionTime -and $historyItem.EndExecutionTime) {{
            $duration = [Math]::Max(0, ($historyItem.EndExecutionTime - $historyItem.StartExecutionTime).TotalMilliseconds)
        }}
        $command64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($historyItem.CommandLine))
        $cwd64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Location).Path))
        $timestamp = [DateTimeOffset]::Now.ToString("o")
        $arguments = @("note", "--command-b64", $command64, "--cwd-b64", $cwd64, "--exit-code", "$exitCode", "--duration-ms", "$duration", "--occurred-at", "$timestamp")
        try {{ Start-Process -FilePath "ghost" -ArgumentList $arguments -WindowStyle Hidden | Out-Null }} catch {{ }}
    }}
    & $global:PoltergeistOriginalPrompt
}}
{HOOK_END}'''


def install_powershell_hook(profile: Path, pending_file: Path | None = None) -> Path:
    """Back up and append the hook. Caller is responsible for showing a preview/confirmation."""
    profile = Path(profile)
    profile.parent.mkdir(parents=True, exist_ok=True)
    existing = profile.read_text(encoding="utf-8") if profile.exists() else ""
    if HOOK_BEGIN in existing:
        return profile
    if profile.exists():
        backup = profile.with_suffix(profile.suffix + ".poltergeist.bak")
        if not backup.exists():
            shutil.copy2(profile, backup)
    profile.write_text(
        existing.rstrip() + "\n\n" + powershell_hook(pending_file) + "\n", encoding="utf-8"
    )
    return profile


def uninstall_powershell_hook(profile: Path) -> bool:
    """Remove only the marked Poltergeist block, preserving other profile content."""
    profile = Path(profile)
    if not profile.exists():
        return False
    text = profile.read_text(encoding="utf-8")
    start = text.find(HOOK_BEGIN)
    end = text.find(HOOK_END, start)
    if start < 0 or end < 0:
        return False
    end += len(HOOK_END)
    cleaned = (text[:start].rstrip() + "\n" + text[end:].lstrip()).strip()
    if cleaned:
        profile.write_text(cleaned + "\n", encoding="utf-8")
    else:
        profile.unlink()
    return True
