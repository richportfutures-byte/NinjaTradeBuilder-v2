from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .es import compile_es_packet, write_compiled_packet
from .sources import (
    JsonHistoricalMarketDataSource,
    JsonManualOverlaySource,
    PacketCompilerSourceError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ninjatradebuilder.packet_compiler.cli",
        description="Compile one validated historical_packet_v1 JSON file for ES.",
    )
    parser.add_argument("--contract", choices=("ES",), default="ES")
    parser.add_argument("--historical-input", required=True, help="Path to ES historical bars JSON.")
    parser.add_argument("--overlay", required=True, help="Path to ES manual overlay JSON.")
    parser.add_argument("--output", required=True, help="Path to write packet.json.")
    parser.add_argument(
        "--provenance-output",
        help="Optional path to write packet provenance JSON. Defaults to packet.provenance.json.",
    )
    return parser


def run_cli(argv: list[str] | None = None, *, stdout: Any = None, stderr: Any = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        historical_input = JsonHistoricalMarketDataSource(Path(args.historical_input)).load_es_input()
        overlay = JsonManualOverlaySource(Path(args.overlay)).load_es_overlay()
        artifact = compile_es_packet(historical_input, overlay)
        output_path, provenance_path = write_compiled_packet(
            artifact,
            output_path=Path(args.output),
            provenance_output_path=Path(args.provenance_output) if args.provenance_output else None,
        )
    except (PacketCompilerSourceError, ValueError) as exc:
        stderr.write(f"ERROR: {exc}\n")
        return 2

    stdout.write(
        json.dumps(
            {
                "contract": args.contract,
                "packet_path": str(output_path),
                "provenance_path": str(provenance_path),
                "packet_schema": artifact.packet.schema_name,
                "market_timestamp": artifact.packet.market_packet.timestamp.isoformat().replace(
                    "+00:00", "Z"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    stdout.write("\n")
    return 0


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
