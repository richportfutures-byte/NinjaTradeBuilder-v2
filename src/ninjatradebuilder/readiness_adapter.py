from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .prompt_assets import MASTER_DOCTRINE_TEMPLATE
from .validation import validate_historical_packet

SUPPORTED_PACKET_READINESS_CONTRACTS = ("ES", "ZN")


def build_readiness_runtime_inputs_from_packet(packet_payload: Mapping[str, Any]) -> dict[str, Any]:
    packet = validate_historical_packet(packet_payload)
    if packet.market_packet.contract not in SUPPORTED_PACKET_READINESS_CONTRACTS:
        raise ValueError(
            "Packet-backed readiness conversion is currently supported for ES and ZN only."
        )

    return {
        "master_doctrine_text": MASTER_DOCTRINE_TEMPLATE,
        "evaluation_timestamp_iso": packet.market_packet.timestamp.isoformat().replace("+00:00", "Z"),
        "challenge_state_json": packet.challenge_state.model_dump(mode="json", by_alias=True),
        "contract_metadata_json": packet.contract_metadata.model_dump(mode="json", by_alias=True),
        "market_packet_json": packet.market_packet.model_dump(mode="json", by_alias=True),
        "contract_specific_extension_json": packet.contract_specific_extension.model_dump(
            mode="json",
            by_alias=True,
        ),
        "attached_visuals_json": packet.attached_visuals.model_dump(mode="json", by_alias=True),
    }
