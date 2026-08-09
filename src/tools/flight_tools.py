from __future__ import annotations

from langchain_core.tools import tool

from src.database.flight_repository import get_flight
from src.database.transit_service import check_transit_window


# =========================================================
# Flight lookup tool
# =========================================================

@tool
def lookup_flight(
    flight_number: str,
    flight_date: str,
) -> dict:
    """
    Look up a specific flight by flight number and date.

    Date format:
    YYYY-MM-DD
    """

    flight = get_flight(
        flight_number,
        flight_date,
    )

    if flight is None:
        return {
            "success": False,
            "flight_number": flight_number,
            "flight_date": flight_date,
            "error": "Flight not found.",
        }

    return {
        "success": True,
        "flight": flight,
    }

# =========================================================
# Transit eligibility tool
# =========================================================

@tool
def check_transit_eligibility(
    arrival_flight_number: str,
    departure_flight_number: str,
) -> dict:
    """
    Check the transit duration between an arrival flight
    and a departure flight.

    Use this tool when the user provides both an arrival
    flight and a departure flight and asks whether the
    transit duration is within the required 5.5 to 24 hour
    window for the Free Singapore Tour.

    The tool retrieves flight data from the database and
    calculates the transit duration using deterministic
    Python logic.
    """

    try:
        result = check_transit_window(
            arrival_flight_number,
            departure_flight_number,
        )

        return {
            "success": True,
            **result,
        }

    except ValueError as exc:

        return {
            "success": False,
            "error": str(exc),
        }