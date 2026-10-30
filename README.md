# Poltergeist

A read-only ghost for your terminal. It remembers redacted command history and offers short,
eerie, funny, or unexpectedly kind whispers. The ghost speaks at the next prompt, so its delay is
part of the haunting.

## 30-second quickstart

Requires Python 3.11+ and PowerShell. Run `ghost init` from a PowerShell session. Ollama is
optional; hand-written whispers work without it.

```powershell
python -m pip install -e .
ghost init
```

`ghost init` previews the PowerShell profile change, backs up an existing profile, asks for a
persona, and checks the local Ollama server. If Ollama is running but the model is missing, it can
ask that local server to pull the selected model. The default is `llama3.2:3b`; set
`POLTERGEIST_MODEL=qwen2.5:3b` to choose the other suggested model.

Restart PowerShell after setup. Try a few commands, then run `ghost mood` or `ghost remember`.

## What it does

- Captures PowerShell command text, exit status, elapsed time, working directory, and timestamp.
- Redacts command text before SQLite persistence or model prompts.
- Makes model requests only to a loopback Ollama URL. There is no telemetry.
- Runs inference in a detached `ghost note` process. If the answer is late, it is skipped for that
  prompt; the shell does not wait for the model.
- Falls back to at least 40 offline whispers for each built-in persona.
- `ghost remember` asks a local model to narrate SQL-derived history, or joins those facts when the
  model is unavailable.
- `ghost hush 30m` pauses whispers temporarily; `ghost quiet-hours 23:00-07:00` sets a local-time
  quiet window.
- `ghost exorcise` removes the marked PowerShell hook, settings, pending whisper, and local history.

## Safety promises

- The ghost never executes, edits, blocks, or replaces a command. It only displays text.
- Values after password/token flags (`-p`, `--password`, `--token`, and related forms), bearer and
  authorization text, common API-token formats, URL credentials, and environment assignments are
  redacted. The event store also redacts as a second safeguard.
- Only a compact, redacted brief and up to three SQL-derived facts go to Ollama. The whisper
  validator limits length and rejects ungrounded numbers, quotes, and emoji.
- Ollama URLs must be HTTP on `localhost`, `127.0.0.1`, or `::1`; proxy environment settings are
  ignored by the client.
- Profile changes are previewed and require confirmation. An existing profile is backed up before
  the marked hook block is added.
- `NO_COLOR` is respected by the prompt hook.

These protections reduce accidental disclosure. Redaction is pattern-based and cannot guarantee
that every possible secret format is recognized; review the redaction rules before using unusual
credential formats.

## History and privacy

The database is `~/.poltergeist/ghost.db`; preferences are in `~/.poltergeist/config.json`. Both
stay on the machine. The stored command and working directory are redacted; timestamps are kept for
local history facts. `ghost exorcise` removes these files and SQLite sidecar files with the data
directory.

## Personas

Personas live in `src/poltergeist/personas/` as TOML files. Each file needs a `name`, a `style`, at
at least ten `examples` entries, and an `offline` array with at least 40 short lines. Add a TOML file
named after its slug, then select it with `ghost init --persona your-slug`.

The `ofrenda` persona is written as a respectful, warm ancestor-like presence, without imitating a
cultural ritual or using stereotyped language.

## Hardware notes

Ollama and the selected model use local memory and compute; a 3B model can still require several
gigabytes depending on quantization, context, and operating system. The fallback pool has no model
or GPU requirement. Keep the Ollama context small for faster answers.

## Measurement and evaluation

Run the prompt-overhead measurement on Windows with PowerShell:

```powershell
python scripts/measure_latency.py
```

It compares a no-op prompt with the hook's synchronous pending-file read, history lookup, argument
encoding, and detached process start over 200 samples. Benchmark events use a temporary data folder
and do not call the model. It prints median and p95 added time. The target is under 20 ms, but no
benchmark has been recorded for this checkout yet.

Evaluate 50 synthetic situations against local Ollama:

```powershell
python scripts/whisper_eval.py
```

The report includes rejected answers, average model response time, and fallback rate. These values
depend on the local model and hardware and are not claimed until the script is run on that machine.

## Terminal recording

For a short GIF, record a clean PowerShell window with ScreenToGif or the built-in Windows capture
tool. Show `ghost init`'s preview, a few commands, the one-prompt-late whisper, `ghost mood`, and
`ghost exorcise` in a disposable profile. Do not include real command history or credentials. An
asciinema recording can be made from a supported shell if you add bash/zsh integration later.

## Tests and development

```powershell
python -m pip install -e ".[dev]"
pytest
ruff check .
```

The tests cover secret redaction, local-only Ollama URLs, SQLite history facts, whisper validation,
speaking rules, persona loading, and PowerShell profile install/removal using temporary files.

## Limitations

- PowerShell is implemented first. Bash and zsh hooks are not included yet.
- `seance` and the COBOL spirit's language-history fact sheets are not implemented yet.
- Model hallucination checks currently validate numbers and output shape; they cannot prove every
  natural-language claim is grounded. Offline fallback is deterministic and hand-written.
- Prompt-overhead and model-evaluation results must be recorded on the target computer before they
  can be quoted in a submission.

## Build notes

Development decisions and surprises are tracked in [docs/BUILD_LOG.md](docs/BUILD_LOG.md).
