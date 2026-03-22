# NinjaTradeBuilder Operator Quickstart

## Purpose

This is the smallest supported local run path for the current branch.

It is intended for operator verification and smoke execution, not production automation.

## Prerequisites

- Python `3.11+`
- run from the repo root
- `GEMINI_API_KEY` set in the shell environment

Install with:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Canonical model

Use `gemini-3.1-pro-preview` for the current validated branch baseline.

## Minimum smoke path

Preferred CLI form:

```bash
export GEMINI_API_KEY=your_existing_key
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ninjatradebuilder.cli \
  --packet tests/fixtures/packets.valid.json \
  --contract ES
```

- If `--packet` is already a single `historical_packet_v1` JSON object, omit `--contract`.
- `--evaluation-timestamp` is optional. If omitted, the CLI uses `market_packet.timestamp`.
- `--model` is optional. The default is `gemini-3.1-pro-preview`.

Equivalent Python API form:

```python
import json
import os
from pathlib import Path

from google import genai

from ninjatradebuilder import run_pipeline, validate_historical_packet
from ninjatradebuilder.gemini_adapter import GeminiResponsesAdapter

packet = json.loads(Path("tests/fixtures/packets.valid.json").read_text())
es_packet = {
    "$schema": "historical_packet_v1",
    "challenge_state": packet["shared"]["challenge_state"],
    "attached_visuals": packet["shared"]["attached_visuals"],
    "contract_metadata": packet["contracts"]["ES"]["contract_metadata"],
    "market_packet": packet["contracts"]["ES"]["market_packet"],
    "contract_specific_extension": packet["contracts"]["ES"]["contract_specific_extension"],
}

validated_packet = validate_historical_packet(es_packet)
adapter = GeminiResponsesAdapter(
    client=genai.Client(api_key=os.environ["GEMINI_API_KEY"]),
    model="gemini-3.1-pro-preview",
)
result = run_pipeline(
    packet=validated_packet,
    evaluation_timestamp_iso=validated_packet.market_packet.timestamp.isoformat().replace("+00:00", "Z"),
    model_adapter=adapter,
)

print(result.termination_stage)
print(result.final_decision)
```

## What this path guarantees

- prompt-bound contract routing
- strict stage-by-stage schema validation
- fail-closed termination at the first valid no-go stage
- explicit final decision mapping at Stage D
- clear startup failure when `GEMINI_API_KEY` is missing

## What this path does not provide yet

- persistence or audit logging
- retry policy
- structured observability
- deployment-specific handler for Netlify or other serverless targets
