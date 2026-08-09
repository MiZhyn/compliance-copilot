from __future__ import annotations

from src.database.fst_recommendation_service import (
    FSTEligibilityService,
)


def main() -> None:

    service = (
        FSTEligibilityService()
    )

    result = (
        service.evaluate(
            arrival_flight_number="SQ12",
            arrival_date="2026-08-20",
            departure_flight_number="SQ318",
            departure_date="2026-08-20",
        )
    )

    print(
        "\n===================================="
    )

    print(
        "FST OPERATIONAL ELIGIBILITY TEST"
    )

    print(
        "===================================="
    )

    print(
        "\nArrival:"
    )

    print(
        result.arrival_flight
    )

    print(
        "\nDeparture:"
    )

    print(
        result.departure_flight
    )

    print(
        "\nTransit hours:"
    )

    print(
        result.transit_hours
    )

    print(
        "\n===================================="
    )

    print(
        "ELIGIBLE SESSIONS"
    )

    print(
        "===================================="
    )

    for session in (
        result.eligible_sessions
    ):

        print(
            f"\n{session.session_code}"
        )

        print(
            f"Tour: "
            f"{session.tour_name}"
        )

        print(
            f"Start: "
            f"{session.start_datetime}"
        )

        print(
            f"End: "
            f"{session.end_datetime}"
        )

        print(
            f"Remaining slots: "
            f"{session.remaining_slots}"
        )

    print(
        "\n===================================="
    )

    print(
        "ALL SESSION EVALUATIONS"
    )

    print(
        "===================================="
    )

    for session in (
        result
        .all_session_evaluations
    ):

        print(
            f"\n{session.session_code}"
        )

        print(
            f"{session.tour_name}"
        )

        print(
            f"Eligible: "
            f"{session.eligible}"
        )

        if session.reasons:

            for reason in (
                session.reasons
            ):

                print(
                    f"- {reason}"
                )

        else:

            print(
                "- All operational checks passed."
            )


if __name__ == "__main__":
    main()