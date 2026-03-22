from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ninjatradebuilder.readiness_adapter import build_readiness_runtime_inputs_from_packet

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _packet_payload(contract: str) -> dict:
    fixture = json.loads((FIXTURES_DIR / "packets.valid.json").read_text())
    return {
        "$schema": "historical_packet_v1",
        "challenge_state": fixture["shared"]["challenge_state"],
        "attached_visuals": fixture["shared"]["attached_visuals"],
        "contract_metadata": fixture["contracts"][contract]["contract_metadata"],
        "market_packet": fixture["contracts"][contract]["market_packet"],
        "contract_specific_extension": fixture["contracts"][contract]["contract_specific_extension"],
    }


def test_build_readiness_runtime_inputs_from_valid_zn_packet() -> None:
    runtime_inputs = build_readiness_runtime_inputs_from_packet(_packet_payload("ZN"))

    assert runtime_inputs["evaluation_timestamp_iso"] == "2026-01-14T15:05:00Z"
    assert runtime_inputs["contract_metadata_json"]["contract"] == "ZN"
    assert runtime_inputs["market_packet_json"]["contract"] == "ZN"
    assert runtime_inputs["contract_specific_extension_json"]["contract"] == "ZN"
    assert runtime_inputs["challenge_state_json"]["max_position_size_by_contract"]["ZN"] == 4
    assert "MASTER DOCTRINE" in runtime_inputs["master_doctrine_text"]


def test_build_readiness_runtime_inputs_from_valid_es_packet() -> None:
    runtime_inputs = build_readiness_runtime_inputs_from_packet(_packet_payload("ES"))

    assert runtime_inputs["evaluation_timestamp_iso"] == "2026-01-14T15:05:00Z"
    assert runtime_inputs["contract_metadata_json"]["contract"] == "ES"
    assert runtime_inputs["market_packet_json"]["contract"] == "ES"
    assert runtime_inputs["contract_specific_extension_json"]["contract"] == "ES"
    assert runtime_inputs["challenge_state_json"]["max_position_size_by_contract"]["ES"] == 2
    assert "MASTER DOCTRINE" in runtime_inputs["master_doctrine_text"]


def test_build_readiness_runtime_inputs_rejects_unsupported_contract() -> None:
    with pytest.raises(ValueError) as exc_info:
        build_readiness_runtime_inputs_from_packet(_packet_payload("CL"))

    assert "ES and ZN only" in str(exc_info.value)


def test_build_readiness_runtime_inputs_rejects_malformed_packet() -> None:
    with pytest.raises(ValueError) as exc_info:
        build_readiness_runtime_inputs_from_packet({"packet": "not-a-historical-packet"})

    assert "challenge_state" in str(exc_info.value)


def test_build_readiness_runtime_inputs_rejects_missing_required_fields() -> None:
    invalid_packet = copy.deepcopy(_packet_payload("ZN"))
    invalid_packet["market_packet"].pop("current_price")

    with pytest.raises(ValueError) as exc_info:
        build_readiness_runtime_inputs_from_packet(invalid_packet)

    assert "current_price" in str(exc_info.value)
