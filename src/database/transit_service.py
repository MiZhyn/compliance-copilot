from __future__ import annotations

from datetime import datetime


def get_effective_datetime(
    flight: dict,
) -> datetime:
    """
    Prefer estimated datetime when available.
    Otherwise fall back to scheduled datetime.
    """

    value = (
        flight.get(
            "estimated_datetime"
        )
        or flight.get(
            "scheduled_datetime"
        )
    )

    if not value:

        raise ValueError(
            "Flight has no estimated or "
            "scheduled datetime."
        )

    return datetime.fromisoformat(
        value
    )


def calculate_transit_hours(
    arrival_flight: dict,
    departure_flight: dict,
) -> float:
    """
    Deterministically calculate transit duration.

    LLM is deliberately not used for arithmetic.
    """

    arrival_datetime = (
        get_effective_datetime(
            arrival_flight
        )
    )

    departure_datetime = (
        get_effective_datetime(
            departure_flight
        )
    )

    duration = (
        departure_datetime
        -
        arrival_datetime
    )

    hours = (
        duration.total_seconds()
        / 3600
    )

    if hours < 0:

        raise ValueError(
            "Departure occurs before arrival."
        )

    return round(
        hours,
        2,
    )