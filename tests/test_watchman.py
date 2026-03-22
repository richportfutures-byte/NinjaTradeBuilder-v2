from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ninjatradebuilder.readiness_adapter import build_readiness_runtime_inputs_from_packet
from ninjatradebuilder.watchman import build_watchman_context_from_runtime_inputs

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


def _recheck_trigger() -> dict[str, str]:
    return {
        "trigger_family": "recheck_at_time",
        "recheck_at_time": "2026-01-14T15:15:00Z",
    }


@pytest.mark.parametrize(
    ("contract", "expected_macro_state"),
    [
        ("ES", "breadth_cash_delta_aligned"),
        ("NQ", "relative_strength_leader"),
        ("CL", "eia_sensitive"),
        ("ZN", "auction_sensitive"),
        ("6E", "dxy_supported_europe_drive"),
        ("MGC", "macro_supportive"),
    ],
)
def test_build_watchman_context_for_each_supported_contract(
    contract: str,
    expected_macro_state: str,
) -> None:
    runtime_inputs = build_readiness_runtime_inputs_from_packet(_packet_payload(contract))

    context = build_watchman_context_from_runtime_inputs(runtime_inputs, _recheck_trigger())

    assert context.contract == contract
    assert context.contract_specific_macro_state == expected_macro_state
    assert context.allowed_hours_state == "inside_allowed_hours"
    assert context.staleness_state == "fresh"
    assert context.visual_readiness_state == "sufficient"
    assert context.missing_inputs == []
    assert "contract_specific_macro_state" in context.rationales


def test_build_watchman_context_rejects_missing_required_runtime_slot() -> None:
    runtime_inputs = build_readiness_runtime_inputs_from_packet(_packet_payload("ZN"))
    runtime_inputs.pop("market_packet_json")

    with pytest.raises(ValueError) as exc_info:
        build_watchman_context_from_runtime_inputs(runtime_inputs, _recheck_trigger())

    assert "market_packet_json" in str(exc_info.value)


def test_build_watchman_context_rejects_malformed_runtime_packet_component() -> None:
    runtime_inputs = build_readiness_runtime_inputs_from_packet(_packet_payload("ES"))
    runtime_inputs["contract_specific_extension_json"] = {"contract": "ES"}

    with pytest.raises(ValueError) as exc_info:
        build_watchman_context_from_runtime_inputs(runtime_inputs, _recheck_trigger())

    assert "breadth" in str(exc_info.value)


def test_build_watchman_context_sets_stale_flag_deterministically() -> None:
    runtime_inputs = build_readiness_runtime_inputs_from_packet(_packet_payload("ES"))
    runtime_inputs["evaluation_timestamp_iso"] = "2026-01-14T15:20:01Z"

    context = build_watchman_context_from_runtime_inputs(runtime_inputs, _recheck_trigger())

    assert context.staleness_state == "stale"
    assert "stale_market_packet" in context.hard_lockout_flags


def test_build_watchman_context_sets_session_wind_down_flag_deterministically() -> None:
    runtime_inputs = build_readiness_runtime_inputs_from_packet(_packet_payload("ZN"))
    runtime_inputs["evaluation_timestamp_iso"] = "2026-01-14T19:30:00Z"
    runtime_inputs["market_packet_json"]["timestamp"] = "2026-01-14T19:30:00Z"

    context = build_watchman_context_from_runtime_inputs(runtime_inputs, _recheck_trigger())

    assert context.session_wind_down_state == "winding_down"
    assert "session_winding_down" in context.awareness_flags


def test_build_watchman_context_sets_event_lockout_flag_deterministically() -> None:
    runtime_inputs = build_readiness_runtime_inputs_from_packet(_packet_payload("ES"))
    event = runtime_inputs["market_packet_json"]["event_calendar_remainder"][0]
    event["event_state"] = "upcoming"
    event["minutes_until"] = 5
    event.pop("minutes_since", None)

    context = build_watchman_context_from_runtime_inputs(runtime_inputs, _recheck_trigger())

    assert context.event_risk_state == "lockout_active"
    assert "event_lockout_active" in context.hard_lockout_flags
