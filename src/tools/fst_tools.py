from __future__ import annotations

from langchain_core.tools import tool

from src.database.fst_repository import (
    get_fst_sessions_by_date,
)
from src.database.fst_recommendation_service import (
    recommend_fst_sessions,
)


# =========================================================
# Tool 1: list FST sessions
# =========================================================

@tool
def list_fst_sessions(
    service_date: str,
) -> dict:
    """
    Get all Free Singapore Tour sessions for a specific date.

    Use this tool when the user asks what Free Singapore
    Tours are available on a particular date.

    Input date format:
    YYYY-MM-DD
    """

    sessions = get_fst_sessions_by_date(
        service_date
    )

    return {
        "service_date": service_date,
        "session_count": len(sessions),
        "sessions": sessions,
    }


# =========================================================
# Tool 2: recommend FST based on flights
# =========================================================

@tool
def recommend_fst_for_passenger(
    arrival_flight_number: str,
    arrival_flight_date: str,
    departure_flight_number: str,
    departure_flight_date: str,
) -> dict:
    """
    Recommend Free Singapore Tour sessions based on the
    passenger's arrival and departure flights.

    This tool checks:

    - arrival flight time
    - departure flight time
    - tour reporting deadline
    - required departure time
    - remaining tour slots
    - tour session status

    Use this tool when the user provides arrival and
    departure flight information and asks which Free
    Singapore Tours they can join.

    Flight date format:
    YYYY-MM-DD
    """

    try:

        result = recommend_fst_sessions(
            arrival_flight_number=(
                arrival_flight_number
            ),
            arrival_flight_date=(
                arrival_flight_date
            ),
            departure_flight_number=(
                departure_flight_number
            ),
            departure_flight_date=(
                departure_flight_date
            ),
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


# =========================================================
# Local tests
# =========================================================

if __name__ == "__main__":

    print(
        "\n=== Test 1: List FST Sessions ==="
    )

    sessions_result = (
        list_fst_sessions.invoke({
            "service_date": "2026-08-20",
        })
    )

    print(
        sessions_result
    )

    print(
        "\n=== Test 2: Recommend FST ==="
    )

    recommendation_result = (
        recommend_fst_for_passenger.invoke({
            "arrival_flight_number": "SQ12",
            "arrival_flight_date": "2026-08-20",
            "departure_flight_number": "SQ318",
            "departure_flight_date": "2026-08-20",
        })
    )

    print(
        recommendation_result
    )