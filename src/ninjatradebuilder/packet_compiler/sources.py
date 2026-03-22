from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .models import ESHistoricalDataInput, ESManualOverlayInput


class PacketCompilerSourceError(ValueError):
    pass


def _load_json_file(path: Path) -> object:
    if not path.is_file():
        raise PacketCompilerSourceError(f"Source file does not exist: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise PacketCompilerSourceError(f"Source file did not contain valid JSON: {path}") from exc


@dataclass(frozen=True)
class JsonHistoricalMarketDataSource:
    path: Path

    def load_es_input(self) -> ESHistoricalDataInput:
        payload = _load_json_file(self.path)
        try:
            return ESHistoricalDataInput.model_validate(payload)
        except ValidationError as exc:
            raise PacketCompilerSourceError(
                f"Historical ES source payload was invalid: {self.path}"
            ) from exc


@dataclass(frozen=True)
class JsonManualOverlaySource:
    path: Path

    def load_es_overlay(self) -> ESManualOverlayInput:
        payload = _load_json_file(self.path)
        try:
            return ESManualOverlayInput.model_validate(payload)
        except ValidationError as exc:
            raise PacketCompilerSourceError(
                f"Manual ES overlay payload was invalid: {self.path}"
            ) from exc
