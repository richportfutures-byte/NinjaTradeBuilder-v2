from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping

from .runtime import StructuredGenerationRequest

try:
    from google import genai
except ImportError:  # pragma: no cover - exercised only when SDK is absent locally
    genai = None  # type: ignore[assignment]


class GeminiAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class GeminiResponsesAdapter:
    client: Any
    model: str

    @classmethod
    def from_default_client(cls, *, model: str) -> "GeminiResponsesAdapter":
        if genai is None:
            raise ImportError("google-genai SDK is required to construct the default Gemini client.")
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise GeminiAdapterError(
                "Gemini API key is required via GEMINI_API_KEY or GOOGLE_API_KEY."
            )
        return cls(client=genai.Client(api_key=api_key), model=model)

    def generate_structured(self, request: StructuredGenerationRequest) -> Mapping[str, Any]:
        response = self.client.models.generate_content(**self._build_generate_params(request))
        envelope = self._extract_envelope(response)
        self._validate_boundary(request, envelope)

        payload = envelope["payload"]
        if not isinstance(payload, Mapping):
            raise TypeError("Gemini envelope payload must be a structured object.")

        return dict(payload)

    def _build_generate_params(self, request: StructuredGenerationRequest) -> dict[str, Any]:
        return {
            "model": self.model,
            "contents": request.rendered_prompt,
            "config": {
                "response_mime_type": "application/json",
                "response_json_schema": self._response_envelope_schema(request),
            },
        }

    @staticmethod
    def _response_envelope_schema(request: StructuredGenerationRequest) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "boundary": {
                    "type": "string",
                    "enum": list(request.expected_output_boundaries),
                    "description": (
                        "Boundary selected by the model from the allowed prompt-bound options."
                    ),
                },
                "payload": {
                    "type": "object",
                    "description": GeminiResponsesAdapter._payload_description(request),
                },
            },
            "required": ["boundary", "payload"],
        }

    @staticmethod
    def _payload_description(request: StructuredGenerationRequest) -> str:
        description = (
            "Structured stage payload. Runtime performs final schema validation "
            f"against: {', '.join(request.schema_model_names)}."
        )
        if request.prompt_id == 8:
            description += (
                " For proposed_setup NO_TRADE responses, emit only schema-defined fields: "
                "always include contract and timestamp, use no_trade_reason as the sole reason field, "
                "set all setup-only fields to null, and do not emit extra keys such as "
                "disqualification_reasons or rejection_reasons. For proposed_setup SETUP_PROPOSED "
                "responses, always include outcome exactly as SETUP_PROPOSED, always include "
                "contract and timestamp, set no_trade_reason to null, normalize direction to the "
                "schema enum LONG or SHORT only, restrict setup_class to scalp, "
                "intraday_swing, or session_hold only, provide non-null direction, entry_price, "
                "stop_price, target_1, position_size, risk_dollars, reward_risk_ratio, "
                "setup_class, hold_time_estimate_minutes, rationale, disqualifiers, and "
                "sizing_math, require sizing_math to be a structured object rather than prose, "
                "and enforce target_2 null when position_size is 1 or required when position_size "
                "is greater than 1."
            )
        if request.prompt_id in {2, 3, 4, 5, 6, 7}:
            description += (
                " For sufficiency_gate_output responses, always emit the full schema object: "
                "contract, timestamp, status, missing_inputs, disqualifiers, data_quality_flags, "
                "staleness_check, challenge_state_valid, and event_lockout_detail when applicable. "
                "staleness_check must be an object with packet_age_seconds, stale, and "
                "threshold_seconds, not a string or summary label. Do not emit shorthand fields "
                "such as reason or missing_fields. If the Stage A status is READY, continue to "
                "Stage B and return contract_analysis instead of returning sufficiency_gate_output."
            )
        return description

    def _extract_envelope(self, response: Any) -> Mapping[str, Any]:
        if isinstance(response, Mapping):
            if "text" in response:
                return self._parse_text(response["text"])
            if "boundary" in response and "payload" in response:
                return dict(response)
            raise GeminiAdapterError("Gemini response mapping is missing structured envelope content.")

        text = getattr(response, "text", None)
        if text is None:
            raise GeminiAdapterError("Gemini response is missing text.")
        return self._parse_text(text)

    @staticmethod
    def _parse_text(text: Any) -> Mapping[str, Any]:
        if not isinstance(text, str):
            raise TypeError("Gemini response text must be a JSON string.")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiAdapterError("Gemini response text did not contain valid JSON.") from exc
        if not isinstance(parsed, Mapping):
            raise TypeError("Gemini structured response must decode to an object.")
        if "boundary" not in parsed or "payload" not in parsed:
            raise GeminiAdapterError("Gemini structured response must include boundary and payload.")
        return dict(parsed)

    @staticmethod
    def _validate_boundary(
        request: StructuredGenerationRequest, envelope: Mapping[str, Any]
    ) -> None:
        boundary = envelope["boundary"]
        if not isinstance(boundary, str):
            raise TypeError("Gemini response boundary must be a string.")
        if boundary not in request.expected_output_boundaries:
            raise GeminiAdapterError(
                f"Gemini response boundary {boundary!r} is not allowed for prompt {request.prompt_id}."
            )
