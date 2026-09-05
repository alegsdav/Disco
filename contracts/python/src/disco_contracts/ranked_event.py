"""``RankedEvent`` — the ranking decision for one filing.

Emitted onto ``alert-delivery``. Every number the Discord card shows comes from
here, and every one of them must be reproducible from the feature store at
``decision_time``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ._base import DiscoModel, NonEmptyString, SchemaVersion, Sha256Id, UtcTimestamp


class Scores(DiscoModel):
    """Component scores and the blended final score, all in [0, 1]."""

    materiality: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    prob_unusual_vol: float = Field(
        ge=0.0,
        le=1.0,
        description="Calibrated P(next-session realized volatility is abnormal).",
    )
    final: float = Field(ge=0.0, le=1.0)


class FeatureContribution(DiscoModel):
    """One feature's signed contribution to the decision."""

    feature: NonEmptyString
    contribution: float = Field(
        description=(
            "Logistic-regression coefficient contribution or SHAP value. Signed: "
            "negative means the feature argued against alerting."
        )
    )


class HistoricalAnalogues(DiscoModel):
    """What happened after comparable past filings."""

    sample_size: int = Field(
        ge=0,
        description="Number of analogues found. Zero is a valid, reportable answer.",
    )
    median_next_session_rv: float = Field(
        ge=0.0,
        description="Median next-session realized volatility across the analogues.",
    )
    peer_baseline_rv: float = Field(
        ge=0.0,
        description=(
            "Peer-relative baseline the analogue median is read against."
        ),
    )


class RankedEvent(DiscoModel):
    """A scored filing and the decision on whether to alert."""

    schema_version: Literal["1.0"] = "1.0"

    event_id: Sha256Id
    decision_time: UtcTimestamp = Field(
        description=(
            "The instant the decision was made. Every feature used must satisfy "
            "available_at <= decision_time; this field is what makes that checkable."
        )
    )

    feature_schema_version: SchemaVersion
    model_version: NonEmptyString = Field(
        description=(
            "Model build, for example lgbm-volatility-v0.2.1 or novelty-tfidf-v1."
        )
    )

    scores: Scores
    feature_contributions: list[FeatureContribution] = Field(default_factory=list)
    historical_analogues: HistoricalAnalogues

    alert_policy: NonEmptyString = Field(
        description="Policy that produced should_alert, for example high_signal_v1."
    )
    should_alert: bool
