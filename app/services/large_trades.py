from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Iterable


@dataclass(frozen=True)
class NormalizedTrade:
    venue: str
    market_id: str
    price: float
    size: float
    notional_usd: float
    side: str | None
    outcome: str | None
    occurred_at: datetime
    actor_id: str | None = None
    trade_id: str | None = None


@dataclass(frozen=True)
class LargeTradeSignal:
    trade: NormalizedTrade
    sample_median_usd: float
    multiple_of_median: float | None
    severity: str
    reasons: tuple[str, ...]


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            dt = datetime.fromtimestamp(float(text), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    else:
        raise ValueError("trade timestamp is missing")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_kalshi_trade(item: dict) -> NormalizedTrade:
    price_raw = item.get("yes_price_dollars")
    if price_raw is None and item.get("yes_price") is not None:
        price_raw = float(item["yes_price"]) / 100
    price = float(price_raw)
    size = float(item.get("count_fp") if item.get("count_fp") is not None else item.get("count"))
    if not 0 <= price <= 1 or size <= 0:
        raise ValueError("invalid Kalshi trade")
    market_id = str(item.get("ticker") or "")
    if not market_id:
        raise ValueError("Kalshi trade ticker is missing")
    return NormalizedTrade(
        venue="kalshi",
        market_id=market_id,
        price=price,
        size=size,
        notional_usd=round(price * size, 4),
        side=str(item.get("taker_side")) if item.get("taker_side") else None,
        outcome=str(item.get("taker_outcome_side")) if item.get("taker_outcome_side") else None,
        occurred_at=_as_datetime(item.get("created_time")),
        actor_id=None,
        trade_id=str(item.get("trade_id")) if item.get("trade_id") else None,
    )


def normalize_polymarket_trade(item: dict) -> NormalizedTrade:
    price = float(item.get("price"))
    size = float(item.get("size"))
    if not 0 <= price <= 1 or size <= 0:
        raise ValueError("invalid Polymarket trade")
    market_id = str(item.get("conditionId") or item.get("condition_id") or "")
    if not market_id:
        raise ValueError("Polymarket condition id is missing")
    actor = item.get("proxyWallet") or item.get("proxy_wallet")
    return NormalizedTrade(
        venue="polymarket",
        market_id=market_id,
        price=price,
        size=size,
        notional_usd=round(price * size, 4),
        side=str(item.get("side")) if item.get("side") else None,
        outcome=str(item.get("outcome")) if item.get("outcome") else None,
        occurred_at=_as_datetime(item.get("timestamp")),
        actor_id=str(actor) if actor else None,
        trade_id=str(item.get("transactionHash") or item.get("transaction_hash") or "") or None,
    )


def detect_large_trades(
    trades: Iterable[NormalizedTrade],
    *,
    absolute_floor_usd: float = 5_000,
    median_multiple: float = 8.0,
    limit: int = 20,
) -> list[LargeTradeSignal]:
    """Identify unusually large observed trades without inferring identity or intent."""
    if absolute_floor_usd < 0 or median_multiple <= 1 or limit < 1:
        raise ValueError("invalid large-trade thresholds")
    items = [trade for trade in trades if trade.notional_usd > 0]
    if not items:
        return []
    sample_median = median(trade.notional_usd for trade in items)
    threshold = max(absolute_floor_usd, sample_median * median_multiple)
    signals: list[LargeTradeSignal] = []
    for trade in items:
        if trade.notional_usd < threshold:
            continue
        multiple = trade.notional_usd / sample_median if sample_median > 0 else None
        if trade.notional_usd >= threshold * 5:
            severity = "very_high"
        elif trade.notional_usd >= threshold * 2:
            severity = "high"
        else:
            severity = "elevated"
        reasons = [f"observed trade value ${trade.notional_usd:,.0f}"]
        if multiple is not None:
            reasons.append(f"{multiple:.1f}x sample median")
        if trade.actor_id:
            reasons.append("public venue data includes a wallet identifier")
        else:
            reasons.append("venue data does not identify the trader")
        signals.append(
            LargeTradeSignal(
                trade=trade,
                sample_median_usd=round(sample_median, 4),
                multiple_of_median=None if multiple is None else round(multiple, 2),
                severity=severity,
                reasons=tuple(reasons),
            )
        )
    signals.sort(key=lambda signal: signal.trade.notional_usd, reverse=True)
    return signals[:limit]
