# Build log

## Step 1 — scaffold, config, Ollama client, redactor

- Tried: Git checkout of the supplied repository and its public archive URL.
- Failed: GitHub access could not authenticate in this environment, so the remote checkout was
  unavailable. No supplied credential was used or copied into files.
- Surprised by: The specification asks for fully local inference, so an API key is not needed by
  the Ollama client.
- Decision: Keep the client restricted to loopback HTTP, disable proxy environment use, and redact
  before any persistence. Start with broad secret patterns and expand them with regression cases.
- Whispers: Not implemented in this step.

## Step 2 — SQLite event store and facts

- Tried: Create a compact event table with parameterized SQL and deterministic history facts.
- Failed: No repository-specific schema was available because the named GitHub checkout could not
  be opened.
- Surprised by: Enforcing redaction inside the store as well as in the caller gives a second
  boundary against accidental raw-command persistence.
- Decision: Persist only redacted command text and query exact-command counts, failure counts, and
  most-used working folder. Keep timestamps in UTC.
- Whispers: Not implemented in this step.

## Step 3 — Briefs, personas, validation, and offline fallback

- Tried: Put a compact brief builder and number-grounded validator in front of the model, and keep
  four editable TOML personas with separate example and offline whisper pools.
- Failed: Model quality cannot be measured before a local Ollama model is available.
- Surprised by: A short handwritten pool makes the no-model path useful without adding network
  dependencies.
- Decision: Reject answers with unsupported numbers, quotes, emoji, or excess length; retry once,
  then select a deterministic offline whisper.
- Whispers: No model-generated examples captured yet; the evaluation script creates synthetic
  situations without real user history.

## Step 4 — PowerShell hook, init, exorcise, delayed delivery

- Tried: Add a marked and removable profile block that prints a queued whisper, then launches
  `ghost note` as a hidden detached process for the command that just finished.
- Failed: The upstream repository could not be checked out, so profile behavior has only been
  authored against the requirements rather than an existing codebase.
- Surprised by: Passing the event as base64 arguments avoids shell quoting ambiguity for paths and
  command text; redaction still happens before storage or inference.
- Decision: Preview the profile addition, back up an existing profile once, and preserve unrelated
  profile content during uninstall.
- Whispers: The one-prompt delay is intentional; late answers are not allowed to hold the shell.

## Step 5 — Speak/skip rules, hush, and measurement

- Tried: Keep speaking decisions in local code and add quiet hours, temporary hush, a speed-burst
  skip, and a 200-sample PowerShell overhead script.
- Failed: The under-20-ms target has not been measured on the target Windows machine yet.
- Surprised by: Starting a detached Python process is part of prompt overhead, so the benchmark
  includes the process start while keeping model work out of the timed section.
- Decision: Favor skipping when policy is uncertain; model output cannot trigger a whisper itself.
- Whispers: Offline and model evaluation counts are not yet recorded; see the evaluation script.

## Remember command

- Tried: Build a short story prompt only from SQL summaries: busiest late-night stretch,
  most-failed command, oldest folder, and a command used once.
- Failed: No recorded history is available in a fresh install; the command reports that plainly.
- Surprised by: SQL can supply the factual outline without sending raw event history.
- Decision: Use local Ollama for narration and the SQL facts themselves when Ollama is unavailable.
- Whispers: User-history stories are not generated during development.
