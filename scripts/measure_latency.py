"""Measure the foreground cost of the PowerShell prompt hook over 200 samples."""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=200)
    args = parser.parse_args()
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        print("PowerShell was not found; run this measurement on Windows with the hook shell.")
        return 2
    data_dir = tempfile.TemporaryDirectory(prefix="poltergeist-latency-")
    pending = (Path(data_dir.name) / "pending.txt").as_posix()
    script = r'''
$pending = $args[0]
$n = [int]$args[1]
$dataDir = $args[2]
$env:POLTERGEIST_DATA_DIR = $dataDir
$env:POLTERGEIST_MEASURE_ONLY = "1"
$base = [System.Collections.Generic.List[double]]::new()
$hook = [System.Collections.Generic.List[double]]::new()
$children = [System.Collections.Generic.List[object]]::new()
for ($i = 0; $i -lt $n; $i++) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $null = $true
  $sw.Stop(); $base.Add($sw.Elapsed.TotalMilliseconds)
  [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($pending)) | Out-Null
  [IO.File]::WriteAllText($pending, "sample")
  $sw = [Diagnostics.Stopwatch]::StartNew()
  if ([IO.File]::Exists($pending)) {
    $claimed = "$pending.$([Guid]::NewGuid().ToString('N')).read"
    [IO.File]::Move($pending, $claimed)
    $line = [IO.File]::ReadAllText($claimed)
    [IO.File]::Delete($claimed)
  }
  $null = Get-History -Count 1 | Select-Object -First 1
  $command64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("git status"))
  $cwd64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Location).Path))
  $timestamp = [DateTimeOffset]::Now.ToString("o")
  $arguments = @("note", "--command-b64", $command64, "--cwd-b64", $cwd64, "--exit-code", "0", "--duration-ms", "1", "--occurred-at", "$timestamp")
  try {
    $child = Start-Process -FilePath "ghost" -ArgumentList $arguments -WindowStyle Hidden -PassThru
    $children.Add($child)
  } catch { }
  $sw.Stop(); $hook.Add($sw.Elapsed.TotalMilliseconds)
}
foreach ($child in $children) { $child.WaitForExit() }
if ($children.Count -ne $n) { throw "Could not start all ghost note benchmark processes." }
[pscustomobject]@{ baseline = @($base); hook = @($hook) } | ConvertTo-Json -Compress -Depth 3
'''
    result = subprocess.run(
        [shell, "-NoProfile", "-Command", script, pending, str(args.samples), data_dir.name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        data_dir.cleanup()
        print(result.stderr.strip() or "PowerShell measurement failed.", file=sys.stderr)
        return result.returncode
    try:
        data = json.loads(result.stdout.strip().splitlines()[-1])
        baseline, hook = data["baseline"], data["hook"]
        added = [max(0.0, h - b) for b, h in zip(baseline, hook, strict=True)]
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        data_dir.cleanup()
        print(f"Could not parse PowerShell results: {exc}", file=sys.stderr)
        return 1

    def percentile(values: list[float], p: float) -> float:
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * p))]

    print(f"Samples: {len(added)}")
    print(f"Median added prompt overhead: {statistics.median(added):.3f} ms")
    print(f"p95 added prompt overhead: {percentile(added, 0.95):.3f} ms")
    data_dir.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
