"""Trading session filter — adjusts strategy weights based on time of day."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class TradingSession(str, enum.Enum):
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    OFF_HOURS = "off_hours"


SESSION_RANGES = {
    TradingSession.ASIAN: (0, 8),
    TradingSession.LONDON: (8, 16),
    TradingSession.NEW_YORK: (13, 21),
    TradingSession.OFF_HOURS: (21, 24),
}

# Default strategy weights per session (1.0 = fully active)
DEFAULT_WEIGHTS: dict[TradingSession, dict[str, float]] = {
    TradingSession.ASIAN: {
        "liquidity_sweep": 0.3,
        "trend_continuation": 0.3,
        "breakout_expansion": 1.0,
        "ema_momentum": 0.5,
    },
    TradingSession.LONDON: {
        "liquidity_sweep": 1.0,
        "trend_continuation": 1.0,
        "breakout_expansion": 0.5,
        "ema_momentum": 0.7,
    },
    TradingSession.NEW_YORK: {
        "liquidity_sweep": 1.0,
        "trend_continuation": 1.0,
        "breakout_expansion": 1.0,
        "ema_momentum": 1.0,
    },
    TradingSession.OFF_HOURS: {
        "liquidity_sweep": 0.5,
        "trend_continuation": 0.5,
        "breakout_expansion": 0.5,
        "ema_momentum": 0.5,
    },
}

SESSION_POSITION_MULTIPLIERS: dict[TradingSession, float] = {
    TradingSession.ASIAN: 0.8,
    TradingSession.LONDON: 1.0,
    TradingSession.NEW_YORK: 1.0,
    TradingSession.OFF_HOURS: 0.5,
}


@dataclass
class SessionInfo:
    session: TradingSession
    strategy_weights: dict[str, float] = field(default_factory=dict)
    position_size_multiplier: float = 1.0


class SessionFilter:
    """Determine current trading session and recommended strategy weights."""

    def get_current_session(self, utc_now: datetime | None = None) -> SessionInfo:
        if utc_now is None:
            utc_now = datetime.now(timezone.utc)

        hour = utc_now.hour
        session = self._classify_hour(hour)
        return SessionInfo(
            session=session,
            strategy_weights=DEFAULT_WEIGHTS[session].copy(),
            position_size_multiplier=SESSION_POSITION_MULTIPLIERS[session],
        )

    def _classify_hour(self, hour: int) -> TradingSession:
        # New York and London overlap (13-16), prefer New York
        if 13 <= hour < 21:
            return TradingSession.NEW_YORK
        if 8 <= hour < 13:
            return TradingSession.LONDON
        if 0 <= hour < 8:
            return TradingSession.ASIAN
        return TradingSession.OFF_HOURS

    def format_for_prompt(self, info: SessionInfo) -> str:
        lines = [
            f"## Trading Session: {info.session.value.replace('_', ' ').title()}",
            f"Position size multiplier: {info.position_size_multiplier}",
            "Strategy weights:",
        ]
        for name, weight in sorted(info.strategy_weights.items()):
            lines.append(f"  - {name}: {weight:.1f}")
        return "\n".join(lines)
