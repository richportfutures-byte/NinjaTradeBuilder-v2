from __future__ import annotations

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from ..schemas.contracts import IndexCashTone
from ..schemas.inputs import (
    AttachedVisuals,
    ChallengeState,
    EventCalendarEntry,
    OpeningType,
)


class CompilerStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class HistoricalBar(CompilerStrictModel):
    timestamp: AwareDatetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @model_validator(mode="after")
    def validate_ohlcv(self) -> "HistoricalBar":
        if self.high < self.low:
            raise ValueError("Historical bars require high >= low.")
        if not self.low <= self.open <= self.high:
            raise ValueError("Historical bars require open to be inside the high/low range.")
        if not self.low <= self.close <= self.high:
            raise ValueError("Historical bars require close to be inside the high/low range.")
        if self.volume <= 0:
            raise ValueError("Historical bars require volume > 0.")
        return self


class ESHistoricalDataInput(CompilerStrictModel):
    contract: Literal["ES"] = "ES"
    prior_rth_bars: list[HistoricalBar]
    overnight_bars: list[HistoricalBar]
    current_rth_bars: list[HistoricalBar]
    weekly_open_bar: HistoricalBar

    @model_validator(mode="after")
    def validate_bar_sets(self) -> "ESHistoricalDataInput":
        for field_name in ("prior_rth_bars", "overnight_bars", "current_rth_bars"):
            bars = getattr(self, field_name)
            if not bars:
                raise ValueError(f"{field_name} must contain at least one bar.")
            timestamps = [bar.timestamp for bar in bars]
            if timestamps != sorted(timestamps):
                raise ValueError(f"{field_name} must be sorted by timestamp ascending.")
        return self


class ESManualOverlayInput(CompilerStrictModel):
    contract: Literal["ES"] = "ES"
    challenge_state: ChallengeState
    attached_visuals: AttachedVisuals
    current_session_vah: float
    current_session_val: float
    current_session_poc: float
    previous_session_vah: float
    previous_session_val: float
    previous_session_poc: float
    avg_20d_session_range: float
    cumulative_delta: float
    current_volume_vs_average: float
    opening_type: OpeningType
    major_higher_timeframe_levels: list[float] | None = Field(default=None, max_length=5)
    key_hvns: list[float] | None = Field(default=None, max_length=3)
    key_lvns: list[float] | None = Field(default=None, max_length=3)
    singles_excess_poor_high_low_notes: str | None = None
    event_calendar_remainder: list[EventCalendarEntry]
    cross_market_context: dict[str, Any] | None
    data_quality_flags: list[str] | None
    breadth: str
    index_cash_tone: IndexCashTone
