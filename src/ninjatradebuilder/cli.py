from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .config import DEFAULT_GEMINI_MODEL, ConfigError, load_gemini_startup_config
from .gemini_adapter import GeminiResponsesAdapter, genai
from .pipeline import PipelineExecutionResult, run_pipeline
from .schemas.packet import HistoricalPacket
from .validation import validate_historical_packet

SUPPORTED_CONTRACTS = ("ES", "NQ", "CL", "ZN", "6E", "MGC")
ClientFactory = Callable[[str], Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ninjatradebuilder.cli",
        description="Run the validated NinjaTradeBuilder pipeline on one packet file.",
    )
    parser.add_argument(
        "--packet",
        required=True,
        help="Path to a historical_packet_v1 JSON file, or a contract bundle like tests/fixtures/packets.valid.json.",
    )
    parser.add_argument(
        "--contract",
        choices=SUPPORTED_CONTRACTS,
        help="Required only when --packet points to a multi-contract bundle.",
    )
    parser.add_argument(
        "--evaluation-timestamp",
        help="Optional override for the evaluation timestamp. Defaults to market_packet.timestamp.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_GEMINI_MODEL,
        help=f"Gemini model identifier. Defaults to {DEFAULT_GEMINI_MODEL}.",
    )
    return parser


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"Packet file does not exist: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Packet file did not contain valid JSON: {path}") from exc


def _extract_bundle_packet(bundle: Mapping[str, Any], contract: str) -> dict[str, Any]:
    if contract not in bundle.get("contracts", {}):
        raise ValueError(f"Bundle packet does not contain contract {contract}.")

    return {
        "$schema": "historical_packet_v1",
        "challenge_state": bundle["shared"]["challenge_state"],
        "attached_visuals": bundle["shared"]["attached_visuals"],
        "contract_metadata": bundle["contracts"][contract]["contract_metadata"],
        "market_packet": bundle["contracts"][contract]["market_packet"],
        "contract_specific_extension": bundle["contracts"][contract]["contract_specific_extension"],
    }


def load_packet_input(path: Path, *, contract: str | None) -> HistoricalPacket:
    payload = _load_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError("Packet file must decode to a JSON object.")

    if payload.get("$schema") == "historical_packet_v1":
        return validate_historical_packet(payload)

    if "shared" in payload and "contracts" in payload:
        if not contract:
            raise ValueError("Bundle packet files require --contract.")
        return validate_historical_packet(_extract_bundle_packet(payload, contract))

    raise ValueError(
        "Packet file must be a historical_packet_v1 object or a supported multi-contract bundle."
    )


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True)
    if is_dataclass(value):
        return {key: _normalize_for_json(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {key: _normalize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_for_json(item) for item in value]
    return value


def serialize_pipeline_result(result: PipelineExecutionResult) -> dict[str, Any]:
    return _normalize_for_json(result)


def _build_client(api_key: str, client_factory: ClientFactory | None) -> Any:
    if client_factory is not None:
        return client_factory(api_key)
    if genai is None:
        raise ImportError("google-genai SDK is required for Gemini CLI execution.")
    return genai.Client(api_key=api_key)


def run_cli(
    argv: list[str] | None = None,
    *,
    stdout: Any = None,
    stderr: Any = None,
    client_factory: ClientFactory | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_gemini_startup_config(model=args.model)
        packet = load_packet_input(Path(args.packet), contract=args.contract)
        evaluation_timestamp = (
            args.evaluation_timestamp
            or packet.market_packet.timestamp.isoformat().replace("+00:00", "Z")
        )
        adapter = GeminiResponsesAdapter(
            client=_build_client(config.api_key, client_factory),
            model=config.model,
        )
        result = run_pipeline(
            packet=packet,
            evaluation_timestamp_iso=evaluation_timestamp,
            model_adapter=adapter,
        )
    except (ConfigError, ImportError, ValueError) as exc:
        stderr.write(f"ERROR: {exc}\n")
        return 2

    stdout.write(json.dumps(serialize_pipeline_result(result), indent=2, sort_keys=True))
    stdout.write("\n")
    return 0


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
