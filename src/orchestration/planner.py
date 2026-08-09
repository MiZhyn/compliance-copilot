from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field


# =========================================================
# Paths / environment
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

load_dotenv(
    PROJECT_ROOT / ".env"
)


# =========================================================
# Configuration
# =========================================================

DEFAULT_ANTHROPIC_MODEL = (
    "claude-sonnet-4-6"
)


# =========================================================
# Structured Travel Request
# =========================================================

class TravelRequest(BaseModel):
    """
    Structured representation of the user's request.

    Planner responsibilities:
    - extract user-provided facts
    - normalize entities
    - identify requested checks
    - identify missing required inputs

    Planner must NOT:
    - determine visa eligibility
    - determine FST eligibility
    - calculate transit duration
    - query operational databases
    """

    # -----------------------------------------------------
    # Traveller
    # -----------------------------------------------------

    passport_country: str | None = Field(
        default=None,
        description=(
            "Passport issuing country. "
            "For example: India, China, "
            "United Kingdom."
        ),
    )

    # -----------------------------------------------------
    # Arrival
    # -----------------------------------------------------

    arrival_flight: str | None = Field(
        default=None,
        description=(
            "Arrival flight number, normalized "
            "to uppercase without spaces. "
            "Example: SQ12."
        ),
    )

    arrival_date: str | None = Field(
        default=None,
        description=(
            "Arrival date in YYYY-MM-DD format."
        ),
    )

    # -----------------------------------------------------
    # Departure
    # -----------------------------------------------------

    departure_flight: str | None = Field(
        default=None,
        description=(
            "Departure flight number, normalized "
            "to uppercase without spaces. "
            "Example: SQ318."
        ),
    )

    departure_date: str | None = Field(
        default=None,
        description=(
            "Departure date in YYYY-MM-DD format."
        ),
    )

    # -----------------------------------------------------
    # Requested checks
    # -----------------------------------------------------

    check_visa: bool = Field(
        default=False,
        description=(
            "True when the user asks about visa, "
            "entry requirements, VFTF, or whether "
            "they can enter Singapore."
        ),
    )

    check_fst: bool = Field(
        default=False,
        description=(
            "True when the user asks about the "
            "Free Singapore Tour, FST, or which "
            "tour session they can join."
        ),
    )

    check_transit: bool = Field(
        default=False,
        description=(
            "True when the requested task requires "
            "checking the time between arrival "
            "and departure."
        ),
    )

    # -----------------------------------------------------
    # Missing information
    # -----------------------------------------------------

    missing_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Required information missing from "
            "the user's request."
        ),
    )


# =========================================================
# Travel Planner
# =========================================================

class TravelPlanner:
    """
    Natural language
        ↓
    Structured TravelRequest

    The planner only decides:

    - what the user provided
    - what the user wants checked
    - what information is missing

    It does NOT decide the final answer.
    """

    def __init__(
        self,
    ) -> None:

        api_key = os.getenv(
            "ANTHROPIC_API_KEY"
        )

        if not api_key:

            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Add it to the project .env file."
            )

        model_name = os.getenv(
            "ANTHROPIC_MODEL",
            DEFAULT_ANTHROPIC_MODEL,
        )

        print(
            f"Planner model: "
            f"{model_name}"
        )

        self.llm = ChatAnthropic(
            model=model_name,
            temperature=0,
            max_tokens=1000,
        )

        self.structured_llm = (
            self.llm.with_structured_output(
                TravelRequest,
                method="json_schema",
            )
        )


    # =====================================================
    # Normalize flight number
    # =====================================================

    @staticmethod
    def _normalize_flight_number(
        flight_number: str | None,
    ) -> str | None:
        """
        Defensive normalization after LLM extraction.

        Examples:
            "sq 12" -> "SQ12"
            " Sq318 " -> "SQ318"
        """

        if not flight_number:
            return None

        return (
            flight_number
            .replace(" ", "")
            .strip()
            .upper()
        )


    # =====================================================
    # Validate ISO date
    # =====================================================

    @staticmethod
    def _validate_date(
        value: str | None,
    ) -> str | None:
        """
        Keep normalized ISO date only.

        Planner normally produces YYYY-MM-DD,
        but this adds a deterministic validation layer.
        """

        if not value:
            return None

        try:

            parsed = datetime.strptime(
                value,
                "%Y-%m-%d",
            )

        except ValueError:

            raise ValueError(
                "Planner returned invalid date: "
                f"{value}"
            )

        return parsed.strftime(
            "%Y-%m-%d"
        )


    # =====================================================
    # Recalculate missing fields deterministically
    # =====================================================

    @staticmethod
    def _get_missing_fields(
        request: TravelRequest,
    ) -> list[str]:
        """
        Do not rely entirely on the LLM for
        missing-field validation.

        Required fields depend on requested action.
        """

        missing: list[str] = []

        # -------------------------------------------------
        # Visa / immigration check
        # -------------------------------------------------

        if request.check_visa:

            if not request.passport_country:

                missing.append(
                    "passport_country"
                )

        # -------------------------------------------------
        # FST operational timing check
        # -------------------------------------------------

        if request.check_fst:

            required_fst_fields = {
                "arrival_flight":
                    request.arrival_flight,

                "arrival_date":
                    request.arrival_date,

                "departure_flight":
                    request.departure_flight,

                "departure_date":
                    request.departure_date,
            }

            for (
                field_name,
                field_value,
            ) in required_fst_fields.items():

                if not field_value:

                    missing.append(
                        field_name
                    )

        # -------------------------------------------------
        # Explicit transit check
        # -------------------------------------------------

        elif request.check_transit:

            required_transit_fields = {
                "arrival_flight":
                    request.arrival_flight,

                "arrival_date":
                    request.arrival_date,

                "departure_flight":
                    request.departure_flight,

                "departure_date":
                    request.departure_date,
            }

            for (
                field_name,
                field_value,
            ) in required_transit_fields.items():

                if not field_value:

                    missing.append(
                        field_name
                    )

        # Remove duplicates while preserving order.
        return list(
            dict.fromkeys(
                missing
            )
        )


    # =====================================================
    # Plan
    # =====================================================

    def plan(
        self,
        user_query: str,
    ) -> TravelRequest:
        """
        Convert user language into structured intent.
        """

        reference_date = (
            date.today()
            .isoformat()
        )

        prompt = f"""
You are the planning layer of a travel and compliance
copilot.

Your ONLY job is to extract structured information and
identify which downstream checks are required.

REFERENCE DATE:
{reference_date}

USER REQUEST:
{user_query}


GENERAL RULES:

1. Extract facts provided by the user.

2. Do NOT answer the user's question.

3. Do NOT determine visa eligibility.

4. Do NOT determine Free Singapore Tour eligibility.

5. Do NOT calculate transit duration.

6. Do NOT guess flight schedules.

7. Do NOT invent missing information.


PASSPORT COUNTRY:

Extract the passport issuing country when supplied.

Examples:

"Indian passport holder"
→ India

"Chinese passport"
→ China

"UK passport holder"
→ United Kingdom


FLIGHT NUMBER RULES:

Normalize flight numbers to uppercase without spaces.

Examples:

"sq 12"
→ SQ12

"Sq318"
→ SQ318


DATE RULES:

Output all dates in:

YYYY-MM-DD

If the user provides a month and day but no year,
use the next reasonable occurrence relative to the
reference date.

Example:

Reference date:
2026-08-09

User:
"Aug 20"

Result:
2026-08-20

If the user explicitly supplies a year,
preserve that year.

Do not invent a date when the user did not provide
enough information.


INTENT RULES:

Set:

check_visa = true

when the user asks about:

- visa requirements
- entry visa
- whether they need a visa
- Singapore entry requirements
- Visa Free Transit Facility
- VFTF


Set:

check_fst = true

when the user asks about:

- Free Singapore Tour
- FST
- which Free Singapore Tour they can join
- which tour session is available or suitable


Set:

check_transit = true

when:

- the user asks which FST session they can join
  based on arrival/departure flights

- the request requires comparing arrival and
  departure timing

- the user explicitly asks about transit duration


IMPORTANT:

If check_fst=true and the user wants to know which
specific session they can join, transit timing is
required, so check_transit should also be true.


MISSING FIELD GUIDANCE:

For visa checking:

passport_country is normally required.


For specific FST session checking:

arrival_flight
arrival_date
departure_flight
departure_date

are required.


Do not invent missing values.

Return only the structured TravelRequest.
""".strip()

        result = (
            self.structured_llm
            .invoke(
                prompt
            )
        )

        # =================================================
        # Deterministic normalization
        # =================================================

        result.arrival_flight = (
            self._normalize_flight_number(
                result.arrival_flight
            )
        )

        result.departure_flight = (
            self._normalize_flight_number(
                result.departure_flight
            )
        )

        result.arrival_date = (
            self._validate_date(
                result.arrival_date
            )
        )

        result.departure_date = (
            self._validate_date(
                result.departure_date
            )
        )

        if result.passport_country:

            result.passport_country = (
                result
                .passport_country
                .strip()
            )

        # =================================================
        # Deterministic missing-field validation
        # =================================================

        result.missing_fields = (
            self._get_missing_fields(
                result
            )
        )

        return result