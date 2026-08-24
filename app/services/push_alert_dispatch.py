from __future__ import annotations

from dataclasses import dataclass

from fastapi import Response

import app.main as core
from app.routes.public_alert_signals import MarketAlertSnapshot, market_alert_signals
from app.services.web_push import PushDeliveryResult, send_web_push
from app.storage.push_subscriptions import PushAlert, PushSubscriptionStore


@dataclass(frozen=True)
class DispatchSummary:
    evaluated: int
    sent: int
    gone: int
    failed: int


def alert_state(snapshot: MarketAlertSnapshot) -> dict[str, object]:
    return {
        "probability": snapshot.probability,
        "breaking": bool(snapshot.breaking.available and snapshot.breaking.active),
        "execution": bool(
            snapshot.execution.available
            and snapshot.execution.score is not None
            and snapshot.execution.score <= 45
        ),
        "large_key": (
            snapshot.large_trade_activity.latest_signal_key
            if snapshot.large_trade_activity.available
            else None
        ),
        "gap": bool(
            snapshot.cross_platform.equivalent_contracts
            and snapshot.cross_platform.gap_points is not None
            and snapshot.cross_platform.gap_points >= 5
        ),
        "evidence_key": snapshot.evidence.latest_evidence_key if snapshot.evidence.available else None,
        "closing_hours": snapshot.closing.remaining_hours if snapshot.closing.available else None,
    }


def transition_reasons(alert: PushAlert, next_state: dict[str, object]) -> list[str]:
    prefs = alert.preferences
    previous = alert.last_state
    reasons: list[str] = []

    threshold = prefs.get("probability_threshold")
    probability = next_state.get("probability")
    previous_probability = previous.get("probability")
    if isinstance(threshold, (int, float)) and isinstance(probability, (int, float)):
        if probability >= threshold and not (
            isinstance(previous_probability, (int, float)) and previous_probability >= threshold
        ):
            reasons.append(f"probability reached {threshold * 100:.0f}%")

    if prefs.get("breaking") and next_state.get("breaking") and not previous.get("breaking"):
        reasons.append("fresh breaking-move signal")
    if prefs.get("execution") and next_state.get("execution") and not previous.get("execution"):
        reasons.append("weak displayed execution quality")
    if prefs.get("large"):
        next_key = next_state.get("large_key")
        previous_key = previous.get("large_key")
        if next_key and previous_key and next_key != previous_key:
            reasons.append("new unusually large observed trade")
    if prefs.get("gap") and next_state.get("gap") and not previous.get("gap"):
        reasons.append("verified cross-platform gap of at least 5 points")
    if prefs.get("evidence"):
        next_key = next_state.get("evidence_key")
        previous_key = previous.get("evidence_key")
        if next_key and previous_key and next_key != previous_key:
            reasons.append("new attributable evidence")
    closing_hours = prefs.get("closing_hours")
    next_hours = next_state.get("closing_hours")
    previous_hours = previous.get("closing_hours")
    if isinstance(closing_hours, (int, float)) and isinstance(next_hours, (int, float)):
        if next_hours <= closing_hours and not (
            isinstance(previous_hours, (int, float)) and previous_hours <= closing_hours
        ):
            reasons.append(f"entered the {closing_hours:g} hour closing window")
    return reasons


async def dispatch_push_alerts_once(store: PushSubscriptionStore, *, limit: int = 1000) -> DispatchSummary:
    evaluated = sent = gone = failed = 0
    for alert in store.active_alerts(limit):
        evaluated += 1
        try:
            snapshot = await market_alert_signals(Response(), market_id=alert.market_id)
        except Exception:
            failed += 1
            continue
        next_state = alert_state(snapshot)
        reasons = transition_reasons(alert, next_state)
        if not reasons:
            store.update_state(alert.subscription_id, alert.market_id, next_state)
            continue
        try:
            subscription = store.get_active(alert.subscription_id)
            market = core._market_by_id(alert.market_id)
        except (KeyError, Exception):
            failed += 1
            continue
        result: PushDeliveryResult = await send_web_push(
            subscription,
            title="PrediBeacon market alert",
            body=f"{market.title}: " + "; ".join(reasons[:3]) + ".",
            url=f"/markets/{market.slug}",
        )
        if result.state == "sent":
            sent += 1
            store.update_state(alert.subscription_id, alert.market_id, next_state)
        elif result.state == "gone":
            gone += 1
            store.revoke(alert.subscription_id)
        elif result.state == "disabled":
            # Do not consume transitions while VAPID is unavailable.
            continue
        else:
            failed += 1
    return DispatchSummary(evaluated=evaluated, sent=sent, gone=gone, failed=failed)
