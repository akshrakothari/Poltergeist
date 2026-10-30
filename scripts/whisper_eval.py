"""Evaluate grounded whispers on 50 synthetic, non-sensitive situations."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

from poltergeist.config import Config
from poltergeist.ollama import OllamaClient, OllamaError
from poltergeist.personas import load_persona
from poltergeist.whisper import HauntingBrief, valid_whisper


async def evaluate(samples: int, persona_name: str) -> None:
    config = Config.from_env()
    client = OllamaClient(config.ollama_url, config.model)
    persona = load_persona(persona_name)
    situations = [
        HauntingBrief(
            command=["git status", "pytest", "cd project", "python app.py", "git push --force"][i % 5],
            exit_code=1 if i % 7 == 0 else 0,
            time_of_day=["morning", "afternoon", "evening", "late night"][i % 4],
            folder=["garden", "archive", "workshop", "attic", "library"][i % 5],
            facts=(f"This exact command has appeared {i % 9 + 1} times.",),
        )
        for i in range(samples)
    ]
    rejected = 0
    fallback = 0
    elapsed: list[float] = []
    model_unavailable = False
    system = (
        f"You are {persona.name}. {persona.style} Use only facts in the brief, invent no numbers, "
        "dates, names, or advice. One whisper, no more than 30 words, no emoji or quotes."
    )
    for brief in situations:
        rendered = brief.render()
        accepted = False
        if model_unavailable:
            fallback += 1
            continue
        for _attempt in range(2):
            start = time.perf_counter()
            try:
                text = await client.generate(rendered, system=system)
            except OllamaError:
                model_unavailable = True
                break
            elapsed.append(time.perf_counter() - start)
            if valid_whisper(text, rendered):
                accepted = True
                break
            rejected += 1
        if not accepted:
            fallback += 1
    print(f"Situations: {samples}")
    print(f"Rejected by validator: {rejected}")
    print(f"Average model time: {statistics.mean(elapsed) * 1000:.1f} ms" if elapsed else "Average model time: unavailable")
    print(f"Fallback rate: {fallback / samples:.1%}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--persona", default="victorian")
    args = parser.parse_args()
    asyncio.run(evaluate(args.samples, args.persona))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
