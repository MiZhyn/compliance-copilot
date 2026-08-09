from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.database.fst_repository import (
    FSTRepository,
)

from src.database.flight_repository import (
    FlightRepository,
)

from src.database.transit_service import (
    calculate_transit_hours,
    get_effective_datetime,
)


# =========================================================
# Result models
# =========================================================

@dataclass
class SessionEvaluation:

    session_code: str

    tour_name: str

    start_datetime: str

    end_datetime: str

    reporting_deadline: str

    required_departure_after: str

    remaining_slots: int

    status: str

    eligible: bool

    reasons: list[str]


@dataclass
class FSTEligibilityResult:

    arrival_flight: dict

    departure_flight: dict

    transit_hours: float

    eligible_sessions: list[
        SessionEvaluation
    ]

    all_session_evaluations: list[
        SessionEvaluation
    ]


# =========================================================
# Service
# =========================================================

class FSTEligibilityService:
    """
    Determine which FST sessions are operationally
    feasible based on flight and session data.

    Important:

    This service evaluates deterministic timing /
    availability conditions only.

    Policy requirements such as immigration / visa
    eligibility still come from RAG.
    """

    def __init__(
        self,
    ) -> None:

        self.flight_repository = (
            FlightRepository()
        )

        self.fst_repository = (
            FSTRepository()
        )


    def evaluate(
        self,
        arrival_flight_number: str,
        arrival_date: str,
        departure_flight_number: str,
        departure_date: str,
    ) -> FSTEligibilityResult:

        # =================================================
        # 1. Load arrival flight
        # =================================================

        arrival_flight = (
            self.flight_repository
            .get_flight(
                flight_number=(
                    arrival_flight_number
                ),
                flight_date=(
                    arrival_date
                ),
                direction="ARRIVAL",
            )
        )

        if arrival_flight is None:

            raise ValueError(
                "Arrival flight not found: "
                f"{arrival_flight_number} "
                f"on {arrival_date}"
            )

        # =================================================
        # 2. Load departure flight
        # =================================================

        departure_flight = (
            self.flight_repository
            .get_flight(
                flight_number=(
                    departure_flight_number
                ),
                flight_date=(
                    departure_date
                ),
                direction="DEPARTURE",
            )
        )

        if departure_flight is None:

            raise ValueError(
                "Departure flight not found: "
                f"{departure_flight_number} "
                f"on {departure_date}"
            )

        # =================================================
        # 3. Deterministic transit calculation
        # =================================================

        transit_hours = (
            calculate_transit_hours(
                arrival_flight=(
                    arrival_flight
                ),
                departure_flight=(
                    departure_flight
                ),
            )
        )

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

        # =================================================
        # 4. Load operational FST sessions
        # =================================================

        sessions = (
            self.fst_repository
            .get_sessions_by_date(
                service_date=(
                    arrival_date
                )
            )
        )

        # =================================================
        # 5. Evaluate every session
        # =================================================

        evaluations: list[
            SessionEvaluation
        ] = []

        for session in sessions:

            reasons: list[str] = []

            reporting_deadline = (
                datetime.fromisoformat(
                    session[
                        "reporting_deadline"
                    ]
                )
            )

            required_departure_after = (
                datetime.fromisoformat(
                    session[
                        "required_departure_after"
                    ]
                )
            )

            # ---------------------------------------------
            # Rule 1:
            # Session must be operationally open.
            # ---------------------------------------------

            if (
                session["status"]
                .upper()
                != "OPEN"
            ):

                reasons.append(
                    "Session is not open."
                )

            # ---------------------------------------------
            # Rule 2:
            # There must be available capacity.
            # ---------------------------------------------

            if (
                session[
                    "remaining_slots"
                ]
                <= 0
            ):

                reasons.append(
                    "No remaining slots."
                )

            # ---------------------------------------------
            # Rule 3:
            # Passenger must arrive early enough to meet
            # the session reporting deadline.
            # ---------------------------------------------

            if (
                arrival_datetime
                >
                reporting_deadline
            ):

                reasons.append(
                    "Arrival is after the "
                    "reporting deadline."
                )

            # ---------------------------------------------
            # Rule 4:
            # Passenger's departure flight must be late
            # enough after this tour.
            # ---------------------------------------------

            if (
                departure_datetime
                <
                required_departure_after
            ):

                reasons.append(
                    "Departure flight is too early "
                    "for this tour session."
                )

            eligible = (
                len(reasons)
                == 0
            )

            evaluation = (
                SessionEvaluation(
                    session_code=(
                        session[
                            "session_code"
                        ]
                    ),

                    tour_name=(
                        session[
                            "tour_name"
                        ]
                    ),

                    start_datetime=(
                        session[
                            "start_datetime"
                        ]
                    ),

                    end_datetime=(
                        session[
                            "end_datetime"
                        ]
                    ),

                    reporting_deadline=(
                        session[
                            "reporting_deadline"
                        ]
                    ),

                    required_departure_after=(
                        session[
                            "required_departure_after"
                        ]
                    ),

                    remaining_slots=(
                        session[
                            "remaining_slots"
                        ]
                    ),

                    status=(
                        session[
                            "status"
                        ]
                    ),

                    eligible=eligible,

                    reasons=reasons,
                )
            )

            evaluations.append(
                evaluation
            )

        eligible_sessions = [
            item
            for item in evaluations
            if item.eligible
        ]

        return FSTEligibilityResult(
            arrival_flight=(
                arrival_flight
            ),

            departure_flight=(
                departure_flight
            ),

            transit_hours=(
                transit_hours
            ),

            eligible_sessions=(
                eligible_sessions
            ),

            all_session_evaluations=(
                evaluations
            ),
        )