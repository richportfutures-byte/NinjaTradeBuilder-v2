from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from ninjatradebuilder.gemini_adapter import GeminiAdapterError, GeminiResponsesAdapter
from ninjatradebuilder.runtime import StructuredGenerationRequest, execute_prompt
from ninjatradebuilder.schemas.outputs import ContractAnalysis


@dataclass
class FakeGeminiResponse:
    text: Any


class FakeModelsClient:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


class FakeGeminiClient:
    def __init__(self, response: Any) -> None:
        self.models = FakeModelsClient(response)


def _stage_ab_inputs(contract: str) -> dict[str, Any]:
    return {
        "master_doctrine_text": "MASTER DOCTRINE",
        "evaluation_timestamp_iso": "2026-01-14T14:05:00Z",
        "challenge_state_json": {"current_balance": 50000},
        "contract_metadata_json": {"contract": contract},
        "market_packet_json": {"contract": contract, "current_price": 72.35},
        "contract_specific_extension_json": {"contract": contract},
        "attached_visuals_json": {"execution_chart_attached": True},
    }


def _stage_ab_inputs_trade_friendly_es() -> dict[str, Any]:
    return {
        "master_doctrine_text": "MASTER DOCTRINE",
        "evaluation_timestamp_iso": "2026-01-14T15:05:00Z",
        "challenge_state_json": {
            "current_balance": 50000,
            "event_lockout_minutes_before": 5,
            "event_lockout_minutes_after": 5,
        },
        "contract_metadata_json": {"contract": "ES"},
        "market_packet_json": {
            "contract": "ES",
            "timestamp": "2026-01-14T15:04:30Z",
            "current_price": 4490.0,
            "session_open": 4484.0,
            "day_open": 4484.0,
            "prior_day_high": 4498.0,
            "prior_day_low": 4472.0,
            "prior_day_close": 4483.0,
            "overnight_high": 4489.0,
            "overnight_low": 4478.0,
            "vwap": 4488.0,
            "current_session_vah": 4489.5,
            "current_session_val": 4483.5,
            "current_session_poc": 4487.5,
            "previous_session_vah": 4486.0,
            "previous_session_val": 4479.0,
            "previous_session_poc": 4482.5,
            "session_range": 11.0,
            "avg_20d_session_range": 24.0,
            "cumulative_delta": 18500,
            "current_volume_vs_average": 1.18,
            "opening_type": "open_drive",
            "event_calendar_remainder": [],
        },
        "contract_specific_extension_json": {
            "contract": "ES",
            "breadth": "strongly_positive",
            "index_cash_tone": "risk_on",
        },
        "attached_visuals_json": {
            "execution_chart_attached": True,
            "daily_chart_attached": True,
        },
    }


def _stage_c_inputs(contract: str) -> dict[str, Any]:
    return {
        "master_doctrine_text": "MASTER DOCTRINE",
        "evaluation_timestamp_iso": "2026-01-14T14:06:00Z",
        "current_price": 4490.0,
        "challenge_state_json": {"max_risk_per_trade_dollars": 1450},
        "contract_metadata_json": {"contract": contract},
        "contract_analysis_json": {"contract": contract, "evidence_score": 6},
    }


def _stage_c_inputs_trade_friendly(contract: str) -> dict[str, Any]:
    return {
        "master_doctrine_text": "MASTER DOCTRINE",
        "evaluation_timestamp_iso": "2026-01-14T14:06:00Z",
        "current_price": 4490.0,
        "challenge_state_json": {"max_risk_per_trade_dollars": 1450},
        "contract_metadata_json": {
            "contract": contract,
            "max_position_size": 2,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "slippage_per_side_ticks": 1,
        },
        "contract_analysis_json": {
            "contract": contract,
            "timestamp": "2026-01-14T14:05:30Z",
            "market_regime": "trending_up",
            "directional_bias": "bullish",
            "key_levels": {
                "support_levels": [4488.0],
                "resistance_levels": [4496.0, 4500.0],
                "pivot_level": 4490.0,
            },
            "evidence_score": 8,
            "confidence_band": "HIGH",
            "value_context": {
                "relative_to_prior_value_area": "above",
                "relative_to_current_developing_value": "above_vah",
                "relative_to_vwap": "above",
                "relative_to_prior_day_range": "inside",
            },
            "structural_notes": "Price is trending above pivot and above value with clean resistance ladder overhead.",
            "outcome": "ANALYSIS_COMPLETE",
            "conflicting_signals": [],
            "assumptions": [],
        },
    }


def _valid_contract_analysis(contract: str) -> dict[str, Any]:
    return {
        "$schema": "contract_analysis_v1",
        "stage": "contract_market_read",
        "contract": contract,
        "timestamp": "2026-01-14T14:06:00Z",
        "market_regime": "range_bound",
        "directional_bias": "bullish",
        "key_levels": {
            "support_levels": [72.1],
            "resistance_levels": [72.8],
            "pivot_level": 72.4,
        },
        "evidence_score": 6,
        "confidence_band": "MEDIUM",
        "value_context": {
            "relative_to_prior_value_area": "inside",
            "relative_to_current_developing_value": "inside_value",
            "relative_to_vwap": "above",
            "relative_to_prior_day_range": "inside",
        },
        "structural_notes": "Price is holding above pivot with one conflicting signal.",
        "outcome": "ANALYSIS_COMPLETE",
        "conflicting_signals": ["delta mixed"],
        "assumptions": [],
    }


def _valid_proposed_setup(contract: str) -> dict[str, Any]:
    return {
        "$schema": "proposed_setup_v1",
        "stage": "setup_construction",
        "contract": contract,
        "timestamp": "2026-01-14T14:07:00Z",
        "outcome": "SETUP_PROPOSED",
        "no_trade_reason": None,
        "direction": "LONG",
        "entry_price": 4490.0,
        "stop_price": 4486.0,
        "target_1": 4498.0,
        "target_2": 4502.0,
        "position_size": 2,
        "risk_dollars": 112.5,
        "reward_risk_ratio": 2.1,
        "setup_class": "intraday_swing",
        "hold_time_estimate_minutes": 45,
        "rationale": "Long from pivot toward resistance ladder.",
        "disqualifiers": [],
        "sizing_math": {
            "stop_distance_ticks": 16.0,
            "risk_per_tick": 12.5,
            "raw_risk_dollars": 100.0,
            "slippage_cost_dollars": 12.5,
            "adjusted_risk_dollars": 112.5,
            "blended_target_distance_ticks": 33.6,
            "blended_reward_dollars": 236.25,
        },
    }


def _minimal_valid_proposed_setup(contract: str) -> dict[str, Any]:
    return {
        "$schema": "proposed_setup_v1",
        "stage": "setup_construction",
        "contract": contract,
        "timestamp": "2026-01-14T14:07:00Z",
        "outcome": "SETUP_PROPOSED",
        "no_trade_reason": None,
        "direction": "LONG",
        "entry_price": 4490.0,
        "stop_price": 4488.0,
        "target_1": 4494.0,
        "target_2": None,
        "position_size": 1,
        "risk_dollars": 37.5,
        "reward_risk_ratio": 2.0,
        "setup_class": "scalp",
        "hold_time_estimate_minutes": 10,
        "rationale": "Bullish bias from contract_analysis supports a scalp to first resistance.",
        "disqualifiers": [],
        "sizing_math": {
            "stop_distance_ticks": 8.0,
            "risk_per_tick": 12.5,
            "raw_risk_dollars": 25.0,
            "slippage_cost_dollars": 12.5,
            "adjusted_risk_dollars": 37.5,
            "blended_target_distance_ticks": 16.0,
            "blended_reward_dollars": 50.0,
        },
    }


def _envelope(boundary: str, payload: dict[str, Any]) -> FakeGeminiResponse:
    return FakeGeminiResponse(text=json.dumps({"boundary": boundary, "payload": payload}))


def _valid_sufficiency_gate_output(contract: str, status: str = "READY") -> dict[str, Any]:
    output = {
        "$schema": "sufficiency_gate_output_v1",
        "stage": "sufficiency_gate",
        "contract": contract,
        "timestamp": "2026-01-14T14:05:00Z",
        "status": status,
        "missing_inputs": [],
        "disqualifiers": [],
        "data_quality_flags": [],
        "staleness_check": {
            "packet_age_seconds": 30,
            "stale": False,
            "threshold_seconds": 300,
        },
        "challenge_state_valid": True,
        "event_lockout_detail": None,
    }
    if status == "INSUFFICIENT_DATA":
        output["disqualifiers"] = ["outside_allowed_hours"]
    return output


def test_request_translation_is_correct() -> None:
    configured_model = "gemini-3.1-pro-preview"
    client = FakeGeminiClient(_envelope("contract_analysis", _valid_contract_analysis("CL")))
    adapter = GeminiResponsesAdapter(client=client, model=configured_model)
    request = StructuredGenerationRequest(
        prompt_id=4,
        rendered_prompt="rendered cl prompt",
        expected_output_boundaries=("sufficiency_gate_output", "contract_analysis"),
        schema_model_names=("SufficiencyGateOutput", "ContractAnalysis"),
    )

    payload = adapter.generate_structured(request)

    assert payload["contract"] == "CL"
    call = client.models.calls[0]
    assert call["model"] == configured_model
    assert call["contents"] == "rendered cl prompt"
    assert call["config"]["response_mime_type"] == "application/json"


def test_response_json_schema_preserves_exact_prompt_bound_boundary_enum() -> None:
    client = FakeGeminiClient(_envelope("contract_analysis", _valid_contract_analysis("CL")))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")
    request = StructuredGenerationRequest(
        prompt_id=4,
        rendered_prompt="rendered cl prompt",
        expected_output_boundaries=("sufficiency_gate_output", "contract_analysis"),
        schema_model_names=("SufficiencyGateOutput", "ContractAnalysis"),
    )

    adapter.generate_structured(request)

    schema = client.models.calls[0]["config"]["response_json_schema"]
    assert schema["properties"]["boundary"]["enum"] == [
        "sufficiency_gate_output",
        "contract_analysis",
    ]


def test_prompt_2_schema_hint_hardens_sufficiency_gate_shape() -> None:
    client = FakeGeminiClient(_envelope("sufficiency_gate_output", _valid_sufficiency_gate_output("ES")))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")
    request = StructuredGenerationRequest(
        prompt_id=2,
        rendered_prompt="rendered es prompt",
        expected_output_boundaries=("sufficiency_gate_output", "contract_analysis"),
        schema_model_names=("SufficiencyGateOutput", "ContractAnalysis"),
    )

    adapter.generate_structured(request)

    payload_description = client.models.calls[0]["config"]["response_json_schema"]["properties"][
        "payload"
    ]["description"]
    assert "always emit the full schema object" in payload_description
    assert "contract, timestamp, status, missing_inputs, disqualifiers" in payload_description
    assert "staleness_check must be an object" in payload_description
    assert "Do not emit shorthand fields such as reason or missing_fields" in payload_description
    assert "If the Stage A status is READY, continue to Stage B and return contract_analysis" in payload_description


def test_prompt_8_schema_hint_hardens_no_trade_shape() -> None:
    client = FakeGeminiClient(_envelope("proposed_setup", _valid_proposed_setup("ES")))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")
    request = StructuredGenerationRequest(
        prompt_id=8,
        rendered_prompt="rendered stage c prompt",
        expected_output_boundaries=("proposed_setup",),
        schema_model_names=("ProposedSetup",),
    )

    adapter.generate_structured(request)

    payload_description = client.models.calls[0]["config"]["response_json_schema"]["properties"][
        "payload"
    ]["description"]
    assert "always include contract and timestamp" in payload_description
    assert "no_trade_reason as the sole reason field" in payload_description
    assert "do not emit extra keys such as disqualification_reasons" in payload_description
    assert "always include outcome exactly as SETUP_PROPOSED" in payload_description
    assert "normalize direction to the schema enum LONG or SHORT only" in payload_description
    assert "restrict setup_class to scalp, intraday_swing, or session_hold only" in payload_description
    assert "sizing_math to be a structured object rather than prose" in payload_description
    assert "set no_trade_reason to null" in payload_description
    assert "target_2 null when position_size is 1" in payload_description


def test_malformed_provider_output_is_rejected() -> None:
    client = FakeGeminiClient(FakeGeminiResponse(text="not json"))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(GeminiAdapterError) as exc_info:
        adapter.generate_structured(
            StructuredGenerationRequest(
                prompt_id=8,
                rendered_prompt="prompt",
                expected_output_boundaries=("proposed_setup",),
                schema_model_names=("ProposedSetup",),
            )
        )

    assert "valid JSON" in str(exc_info.value)


def test_adapter_cannot_bypass_runtime_validation() -> None:
    client = FakeGeminiClient(_envelope("proposed_setup", {"contract": "ES"}))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(ValueError) as exc_info:
        execute_prompt(
            prompt_id=8,
            runtime_inputs=_stage_c_inputs("ES"),
            model_adapter=adapter,
        )

    assert "failed schema validation" in str(exc_info.value)


def test_end_to_end_prompt_8_minimal_setup_through_gemini_adapter() -> None:
    configured_model = "gemini-3.1-pro-preview"
    client = FakeGeminiClient(_envelope("proposed_setup", _minimal_valid_proposed_setup("ES")))
    adapter = GeminiResponsesAdapter(client=client, model=configured_model)

    result = execute_prompt(
        prompt_id=8,
        runtime_inputs=_stage_c_inputs("ES"),
        model_adapter=adapter,
    )

    assert result.output_boundary == "proposed_setup"
    assert result.validated_output.outcome == "SETUP_PROPOSED"
    assert result.validated_output.position_size == 1
    assert result.validated_output.target_2 is None
    assert client.models.calls[0]["model"] == configured_model


def test_end_to_end_prompt_8_trade_friendly_setup_through_gemini_adapter() -> None:
    configured_model = "gemini-3.1-pro-preview"
    client = FakeGeminiClient(_envelope("proposed_setup", _minimal_valid_proposed_setup("ES")))
    adapter = GeminiResponsesAdapter(client=client, model=configured_model)

    result = execute_prompt(
        prompt_id=8,
        runtime_inputs=_stage_c_inputs_trade_friendly("ES"),
        model_adapter=adapter,
    )

    assert result.output_boundary == "proposed_setup"
    assert result.validated_output.outcome == "SETUP_PROPOSED"
    assert result.validated_output.direction == "LONG"
    assert result.validated_output.position_size == 1
    assert client.models.calls[0]["model"] == configured_model


def test_live_like_no_trade_drift_is_rejected() -> None:
    client = FakeGeminiClient(
        _envelope(
            "proposed_setup",
            {
                "$schema": "proposed_setup_v1",
                "stage": "setup_construction",
                "contract": "ES",
                "timestamp": "2026-01-14T14:07:00Z",
                "outcome": "NO_TRADE",
                "no_trade_reason": "directional_bias_unclear",
                "disqualification_reasons": ["directional_bias_unclear"],
            },
        )
    )
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(ValueError) as exc_info:
        execute_prompt(
            prompt_id=8,
            runtime_inputs=_stage_c_inputs("ES"),
            model_adapter=adapter,
        )

    assert "disqualification_reasons" in str(exc_info.value)


def test_live_like_no_trade_missing_contract_and_timestamp_is_rejected() -> None:
    client = FakeGeminiClient(
        _envelope(
            "proposed_setup",
            {
                "$schema": "proposed_setup_v1",
                "stage": "setup_construction",
                "outcome": "NO_TRADE",
                "no_trade_reason": "directional_bias_unclear",
                "direction": None,
                "entry_price": None,
                "stop_price": None,
                "target_1": None,
                "target_2": None,
                "position_size": None,
                "risk_dollars": None,
                "reward_risk_ratio": None,
                "setup_class": None,
                "hold_time_estimate_minutes": None,
                "rationale": None,
                "disqualifiers": None,
                "sizing_math": None,
            },
        )
    )
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(ValueError) as exc_info:
        execute_prompt(
            prompt_id=8,
            runtime_inputs=_stage_c_inputs("ES"),
            model_adapter=adapter,
        )

    message = str(exc_info.value)
    assert "contract" in message
    assert "timestamp" in message


def test_live_like_setup_proposed_missing_contract_and_timestamp_is_rejected() -> None:
    invalid_payload = _minimal_valid_proposed_setup("ES")
    invalid_payload.pop("contract")
    invalid_payload.pop("timestamp")
    client = FakeGeminiClient(_envelope("proposed_setup", invalid_payload))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(ValueError) as exc_info:
        execute_prompt(
            prompt_id=8,
            runtime_inputs=_stage_c_inputs("ES"),
            model_adapter=adapter,
        )

    message = str(exc_info.value)
    assert "contract" in message
    assert "timestamp" in message


def test_live_like_setup_proposed_outcome_direction_and_sizing_math_drift_is_rejected() -> None:
    invalid_payload = _minimal_valid_proposed_setup("ES")
    invalid_payload.pop("outcome")
    invalid_payload["direction"] = "bullish"
    invalid_payload["sizing_math"] = "Max position size is 2 contracts and risk remains below the limit."
    client = FakeGeminiClient(_envelope("proposed_setup", invalid_payload))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(ValueError) as exc_info:
        execute_prompt(
            prompt_id=8,
            runtime_inputs=_stage_c_inputs("ES"),
            model_adapter=adapter,
        )

    message = str(exc_info.value)
    assert "outcome" in message
    assert "LONG" in message
    assert "SHORT" in message
    assert "sizing_math" in message


def test_live_like_setup_proposed_invalid_setup_class_label_is_rejected() -> None:
    invalid_payload = _minimal_valid_proposed_setup("ES")
    invalid_payload["setup_class"] = "intraday_trend"
    client = FakeGeminiClient(_envelope("proposed_setup", invalid_payload))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(ValueError) as exc_info:
        execute_prompt(
            prompt_id=8,
            runtime_inputs=_stage_c_inputs_trade_friendly("ES"),
            model_adapter=adapter,
        )

    message = str(exc_info.value)
    assert "setup_class" in message
    assert "intraday_swing" in message


def test_no_caller_override_can_replace_prompt_bound_validation() -> None:
    client = FakeGeminiClient(_envelope("risk_authorization", _valid_proposed_setup("ES")))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(GeminiAdapterError) as exc_info:
        execute_prompt(
            prompt_id=8,
            runtime_inputs=_stage_c_inputs("ES"),
            model_adapter=adapter,
        )

    assert "not allowed for prompt 8" in str(exc_info.value)


def test_end_to_end_execution_through_gemini_adapter_boundary() -> None:
    configured_model = "gemini-3.1-pro-preview"
    client = FakeGeminiClient(_envelope("contract_analysis", _valid_contract_analysis("CL")))
    adapter = GeminiResponsesAdapter(client=client, model=configured_model)

    result = execute_prompt(
        prompt_id=4,
        runtime_inputs=_stage_ab_inputs("CL"),
        model_adapter=adapter,
    )

    assert result.output_boundary == "contract_analysis"
    assert isinstance(result.validated_output, ContractAnalysis)
    assert result.validated_output.contract == "CL"
    assert client.models.calls[0]["model"] == configured_model


def test_end_to_end_trade_friendly_es_stage_ab_through_gemini_adapter_boundary() -> None:
    configured_model = "gemini-3.1-pro-preview"
    client = FakeGeminiClient(_envelope("contract_analysis", _valid_contract_analysis("ES")))
    adapter = GeminiResponsesAdapter(client=client, model=configured_model)

    result = execute_prompt(
        prompt_id=2,
        runtime_inputs=_stage_ab_inputs_trade_friendly_es(),
        model_adapter=adapter,
    )

    assert result.output_boundary == "contract_analysis"
    assert isinstance(result.validated_output, ContractAnalysis)
    assert result.validated_output.contract == "ES"
    assert client.models.calls[0]["model"] == configured_model


def test_live_like_stage_a_shorthand_insufficiency_is_rejected() -> None:
    client = FakeGeminiClient(
        _envelope(
            "sufficiency_gate_output",
            {
                "status": "INSUFFICIENT_DATA",
                "reason": "outside_allowed_hours",
                "missing_fields": ["session_open"],
                "data_quality_flags": [],
            },
        )
    )
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(ValueError) as exc_info:
        execute_prompt(
            prompt_id=2,
            runtime_inputs=_stage_ab_inputs_trade_friendly_es(),
            model_adapter=adapter,
        )

    message = str(exc_info.value)
    assert "contract" in message
    assert "timestamp" in message
    assert "missing_inputs" in message
    assert "disqualifiers" in message
    assert "staleness_check" in message
    assert "challenge_state_valid" in message
    assert "reason" in message
    assert "missing_fields" in message


def test_live_like_stage_a_string_staleness_check_is_rejected() -> None:
    invalid_payload = _valid_sufficiency_gate_output("ES", status="NEED_INPUT")
    invalid_payload["missing_inputs"] = ["session_open"]
    invalid_payload["staleness_check"] = "pass"
    client = FakeGeminiClient(_envelope("sufficiency_gate_output", invalid_payload))
    adapter = GeminiResponsesAdapter(client=client, model="gemini-3.1-pro-preview")

    with pytest.raises(ValueError) as exc_info:
        execute_prompt(
            prompt_id=2,
            runtime_inputs=_stage_ab_inputs_trade_friendly_es(),
            model_adapter=adapter,
        )

    message = str(exc_info.value)
    assert "staleness_check" in message
    assert "valid dictionary" in message


def test_default_client_fails_closed_when_env_var_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(GeminiAdapterError) as exc_info:
        GeminiResponsesAdapter.from_default_client(model="gemini-3.1-pro-preview")

    assert "GEMINI_API_KEY or GOOGLE_API_KEY" in str(exc_info.value)
