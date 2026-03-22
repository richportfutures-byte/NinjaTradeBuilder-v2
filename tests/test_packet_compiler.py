from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from ninjatradebuilder.cli import run_cli as run_runtime_cli
from ninjatradebuilder.packet_compiler.cli import run_cli as run_compile_cli
from ninjatradebuilder.packet_compiler.es import compile_es_packet
from ninjatradebuilder.validation import validate_historical_packet

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "compiler"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _valid_contract_analysis(contract: str) -> dict:
    return {
        "$schema": "contract_analysis_v1",
        "stage": "contract_market_read",
        "contract": contract,
        "timestamp": "2026-01-14T16:01:00Z",
        "market_regime": "range_bound",
        "directional_bias": "bullish",
        "key_levels": {
            "support_levels": [5018.0],
            "resistance_levels": [5032.0],
            "pivot_level": 5025.0,
        },
        "evidence_score": 6,
        "confidence_band": "MEDIUM",
        "value_context": {
            "relative_to_prior_value_area": "inside",
            "relative_to_current_developing_value": "inside_value",
            "relative_to_vwap": "above",
            "relative_to_prior_day_range": "inside",
        },
        "structural_notes": "Session rotated higher but remains balanced.",
        "outcome": "NO_TRADE",
        "conflicting_signals": ["balance remains intact"],
        "assumptions": [],
    }


def test_compile_es_packet_derives_expected_features_and_validates() -> None:
    artifact = compile_es_packet(
        _load_json("es_historical_input.valid.json"),
        _load_json("es_overlay.valid.json"),
        compiled_at_iso="2026-01-14T16:05:00Z",
    )

    packet = artifact.packet
    validated = validate_historical_packet(packet.model_dump(by_alias=True, mode="json"))

    assert validated.market_packet.contract == "ES"
    assert validated.market_packet.timestamp.isoformat().replace("+00:00", "Z") == "2026-01-14T16:00:00Z"
    assert validated.market_packet.current_price == 5031.0
    assert validated.market_packet.session_open == 5018.0
    assert validated.market_packet.prior_day_high == 5020.0
    assert validated.market_packet.prior_day_low == 5006.0
    assert validated.market_packet.prior_day_close == 5013.0
    assert validated.market_packet.overnight_high == 5022.0
    assert validated.market_packet.overnight_low == 5008.0
    assert validated.market_packet.session_range == 16.0
    assert validated.market_packet.vwap == pytest.approx(5025.5407)
    assert artifact.provenance["field_provenance"]["market_packet.current_price"]["source"] == "historical_bars"
    assert artifact.provenance["derived_features"]["ib_high"]["value"] == 5028.0
    assert artifact.provenance["derived_features"]["ib_low"]["value"] == 5016.0
    assert artifact.provenance["derived_features"]["ib_range"]["value"] == 12.0
    assert artifact.provenance["derived_features"]["weekly_open"]["value"] == 4998.0


def test_compile_es_packet_rejects_unsorted_current_rth_bars() -> None:
    historical_input = _load_json("es_historical_input.valid.json")
    historical_input["current_rth_bars"] = list(reversed(historical_input["current_rth_bars"]))

    with pytest.raises(ValueError, match="current_rth_bars must be sorted"):
        compile_es_packet(historical_input, _load_json("es_overlay.valid.json"))


def test_compiler_cli_writes_packet_and_provenance(tmp_path: Path) -> None:
    output_path = tmp_path / "packet.json"
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_compile_cli(
        [
            "--historical-input",
            str(FIXTURES_DIR / "es_historical_input.valid.json"),
            "--overlay",
            str(FIXTURES_DIR / "es_overlay.valid.json"),
            "--output",
            str(output_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    summary = json.loads(stdout.getvalue())
    assert summary["contract"] == "ES"
    assert summary["packet_path"] == str(output_path)
    assert output_path.is_file()
    assert output_path.with_suffix(".provenance.json").is_file()
    validate_historical_packet(json.loads(output_path.read_text()))


def test_compiled_packet_runs_through_existing_cli(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "packet.json"
    compile_exit_code = run_compile_cli(
        [
            "--historical-input",
            str(FIXTURES_DIR / "es_historical_input.valid.json"),
            "--overlay",
            str(FIXTURES_DIR / "es_overlay.valid.json"),
            "--output",
            str(output_path),
        ]
    )

    assert compile_exit_code == 0
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    stdout = io.StringIO()
    stderr = io.StringIO()

    class FakeGeminiAdapter:
        def __init__(self, *, client, model, timeout_seconds=None, max_retries=0):
            self.client = client

        def generate_structured(self, request):
            return _valid_contract_analysis("ES")

    monkeypatch.setattr("ninjatradebuilder.cli.GeminiResponsesAdapter", FakeGeminiAdapter)

    exit_code = run_runtime_cli(
        [
            "--packet",
            str(output_path),
        ],
        stdout=stdout,
        stderr=stderr,
        client_factory=lambda config: config,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    output = stdout.getvalue()
    assert '"contract": "ES"' in output
    assert '"termination_stage": "contract_market_read"' in output
    assert '"final_decision": "NO_TRADE"' in output
