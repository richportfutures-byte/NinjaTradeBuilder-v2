from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_GEMINI_MODEL = "gemini-3.1-pro-preview"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class GeminiStartupConfig:
    api_key: str
    model: str


def load_gemini_startup_config(*, model: str | None = None) -> GeminiStartupConfig:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ConfigError("GEMINI_API_KEY is required for CLI execution.")

    resolved_model = (model or DEFAULT_GEMINI_MODEL).strip()
    if not resolved_model:
        raise ConfigError("Gemini model name must be non-empty.")

    return GeminiStartupConfig(api_key=api_key, model=resolved_model)
