# NinjaTradeBuilder Operator Quickstart

## Purpose

This is the smallest supported local run path for the current branch.

It is intended for operator verification and smoke execution, not production automation.

## Prerequisites

- Python `3.11+`
- run from the repo root
- `GEMINI_API_KEY` set in the shell environment

Optional provider policy env vars:

- `NINJATRADEBUILDER_GEMINI_MODEL`
  Default: `gemini-3.1-pro-preview`
- `NINJATRADEBUILDER_GEMINI_TIMEOUT_SECONDS`
  Default: `20`
  Minimum: `10`
- `NINJATRADEBUILDER_GEMINI_MAX_RETRIES`
  Default: `1`
- `NINJATRADEBUILDER_GEMINI_RETRY_INITIAL_DELAY_SECONDS`
  Default: `1.0`
- `NINJATRADEBUILDER_GEMINI_RETRY_MAX_DELAY_SECONDS`
  Default: `4.0`

Install with:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Canonical model

Use `gemini-3.1-pro-preview` for the current validated branch baseline.

## Compile one ES historical packet

The compiler is an upstream step. It builds one frozen `historical_packet_v1` JSON file plus a
provenance sidecar. The current v1 compiler supports `ES` only.

Example:

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ninjatradebuilder.packet_compiler.cli \
  --contract ES \
  --historical-input tests/fixtures/compiler/es_historical_input.valid.json \
  --overlay tests/fixtures/compiler/es_overlay.valid.json \
  --output ./build/es.packet.json
```

This writes:

- `./build/es.packet.json`
- `./build/es.packet.provenance.json`

The compiler currently derives and records provenance for:

- prior RTH high / low / close
- overnight high / low
- VWAP
- session range
- initial balance high / low / range
- weekly open

`initial balance` and `weekly open` are recorded in the provenance sidecar because the frozen
runtime packet schema does not have dedicated top-level fields for them.

## Minimum smoke path

Preferred CLI form:

```bash
export GEMINI_API_KEY=your_existing_key
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ninjatradebuilder.cli \
  --packet ./build/es.packet.json \
  --audit-log ./logs/ninjatradebuilder.audit.jsonl
```

- If `--packet` points to a multi-contract bundle like `tests/fixtures/packets.valid.json`, add
  `--contract ES`.
- `--evaluation-timestamp` is optional. If omitted, the CLI uses `market_packet.timestamp`.
- `--model` is optional. The default is `gemini-3.1-pro-preview`.
- `--audit-log` is optional. When supplied, the CLI appends one JSON record per run.
- Gemini requests are bounded by the centralized timeout and retry env vars above.

Aggregate local audit logs with:

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ninjatradebuilder.audit_report \
  --audit-log ./logs/ninjatradebuilder.audit.jsonl
```

The report prints concise counts for:

- success vs failure
- termination_stage
- final_decision
- error_category
- requested_contract

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
- bounded Gemini request policy with explicit timeout/retry behavior
- optional local JSONL audit record for operator debugging
- thin local aggregate audit report for recurring-run visibility

## What this path does not provide yet

- persistent audit sink beyond local JSONL operator logs
- broader structured observability beyond local file-based aggregation
- deployment-specific handler for Netlify or other serverless targets
