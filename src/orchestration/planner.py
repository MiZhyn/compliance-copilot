from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal

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
# Knowledge routing
# =========================================================

KnowledgeTopic = Literal[
    "visa",
    "fst",
    "customs",
]


class KnowledgeRequest(BaseModel):
    """
    One focused RAG retrieval task.

    A compound user question may generate multiple
    KnowledgeRequest objects.
    """

    topic: KnowledgeTopic = Field(
        description=(
            "Knowledge domain for retrieval. "
            "Allowed values: visa, fst, customs."
        ),
    )

    query: str = Field(
        min_length=1,
        description=(
            "A focused retrieval query for this domain. "
            "The query should preserve important entities, "
            "such as country names, tour names, goods, "
            "policy terms, or user constraints."
        ),
    )


# =========================================================
# Structured Travel Request
# =========================================================

class TravelRequest(BaseModel):
    """
    Structured execution plan extracted from the
    current user request.

    Knowledge requirements and operational tool
    requirements are intentionally separated.
    """

    # -----------------------------------------------------
    # Traveller context
    # -----------------------------------------------------

    passport_country: str | None = Field(
        default=None,
        description=(
            "Passport issuing country when relevant. "
            "Example: India, China, United Kingdom."
        ),
    )

    # -----------------------------------------------------
    # Arrival journey
    # -----------------------------------------------------

    arrival_flight: str | None = Field(
        default=None,
        description=(
            "Arrival flight number normalized to "
            "uppercase without spaces. Example: SQ12."
        ),
    )

    arrival_date: str | None = Field(
        default=None,
        description=(
            "Arrival date in YYYY-MM-DD format."
        ),
    )

    # -----------------------------------------------------
    # Departure journey
    # -----------------------------------------------------

    departure_flight: str | None = Field(
        default=None,
        description=(
            "Departure flight number normalized to "
            "uppercase without spaces. Example: SQ318."
        ),
    )

    departure_date: str | None = Field(
        default=None,
        description=(
            "Departure date in YYYY-MM-DD format."
        ),
    )

    # =====================================================
    # Knowledge requirements
    # =====================================================

    knowledge_requests: list[
        KnowledgeRequest
    ] = Field(
        default_factory=list,
        description=(
            "Independent knowledge retrieval tasks needed "
            "to answer the current request. "
            "A compound question may contain several tasks."
        ),
    )

    # =====================================================
    # Operational tool requirements
    # =====================================================

    needs_arrival_flight_lookup: bool = Field(
        default=False,
        description=(
            "True when answering the request requires "
            "actual arrival flight operational data."
        ),
    )

    needs_departure_flight_lookup: bool = Field(
        default=False,
        description=(
            "True when answering the request requires "
            "actual departure flight operational data."
        ),
    )

    needs_transit_calculation: bool = Field(
        default=False,
        description=(
            "True when arrival and departure times must "
            "be compared or transit duration calculated."
        ),
    )

    needs_fst_operational_check: bool = Field(
        default=False,
        description=(
            "True only when the user wants to know which "
            "actual Free Singapore Tour sessions are "
            "operationally feasible based on their flights, "
            "timing, session status, and availability. "
            "General questions about tour details, itinerary, "
            "attractions, or requirements do not require "
            "this operational check."
        ),
    )

    # -----------------------------------------------------
    # Missing information
    # -----------------------------------------------------

    missing_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Required information that is missing from "
            "both the current request and useful previous "
            "conversation context."
        ),
    )


# =========================================================
# Planner
# =========================================================

class TravelPlanner:
    """
    Natural language
        ↓
    Query decomposition
        ↓
    TravelRequest

    The planner decides WHAT needs to be checked.

    It does not:
    - retrieve knowledge
    - query SQLite
    - perform calculations
    - determine the final answer
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
            max_tokens=1600,
        )

        self.structured_llm = (
            self.llm.with_structured_output(
                TravelRequest,
                method="json_schema",
            )
        )


    # =====================================================
    # Normalisation
    # =====================================================

    @staticmethod
    def _normalize_flight_number(
        value: str | None,
    ) -> str | None:

        if not value:

            return None

        return (
            value
            .replace(" ", "")
            .strip()
            .upper()
        )


    @staticmethod
    def _validate_date(
        value: str | None,
    ) -> str | None:

        if not value:

            return None

        try:

            parsed = datetime.strptime(
                value,
                "%Y-%m-%d",
            )

        except ValueError as exc:

            raise ValueError(
                "Planner returned an invalid date: "
                f"{value}"
            ) from exc

        return parsed.strftime(
            "%Y-%m-%d"
        )


    # =====================================================
    # Knowledge request cleanup
    # =====================================================

    @staticmethod
    def _normalize_knowledge_requests(
        requests: list[
            KnowledgeRequest
        ],
    ) -> list[KnowledgeRequest]:
        """
        Remove accidental duplicate retrieval tasks while
        preserving independent topics.
        """

        cleaned: list[
            KnowledgeRequest
        ] = []

        seen: set[
            tuple[str, str]
        ] = set()

        for item in requests:

            query = " ".join(
                item.query.split()
            ).strip()

            key = (
                item.topic,
                query.casefold(),
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            cleaned.append(
                KnowledgeRequest(
                    topic=item.topic,
                    query=query,
                )
            )

        return cleaned


    # =====================================================
    # Deterministic tool dependencies
    # =====================================================

    @staticmethod
    def _apply_tool_dependencies(
        request: TravelRequest,
    ) -> None:
        """
        Enforce deterministic dependencies after the LLM
        produces the initial plan.

        Transit calculation requires both flight lookups.

        An FST operational eligibility check also requires
        arrival/departure data and transit calculation.
        """

        if request.needs_transit_calculation:

            request.needs_arrival_flight_lookup = (
                True
            )

            request.needs_departure_flight_lookup = (
                True
            )

        if request.needs_fst_operational_check:

            request.needs_arrival_flight_lookup = (
                True
            )

            request.needs_departure_flight_lookup = (
                True
            )

            request.needs_transit_calculation = (
                True
            )


    # =====================================================
    # Deterministic missing-field validation
    # =====================================================

    @staticmethod
    def _validate_missing_fields(
        request: TravelRequest,
    ) -> list[str]:
        """
        Preserve semantic missing fields identified by
        the planner, then deterministically validate
        operational tool inputs.
        """

        missing = list(
            request.missing_fields
        )

        if (
            request
            .needs_arrival_flight_lookup
        ):

            if not request.arrival_flight:

                missing.append(
                    "arrival_flight"
                )

            if not request.arrival_date:

                missing.append(
                    "arrival_date"
                )

        if (
            request
            .needs_departure_flight_lookup
        ):

            if not request.departure_flight:

                missing.append(
                    "departure_flight"
                )

            if not request.departure_date:

                missing.append(
                    "departure_date"
                )

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
        conversation_context: str | None = None,
    ) -> TravelRequest:

        reference_date = (
            date.today()
            .isoformat()
        )

        context_text = (
            conversation_context
            or "No previous conversation context."
        )

        prompt = f"""
You are the planning and query-decomposition layer of an
enterprise travel and compliance copilot.

Your ONLY job is to understand the current request and
create a structured execution plan.

REFERENCE DATE:
{reference_date}


PREVIOUS CONVERSATION CONTEXT:

{context_text}


CURRENT USER REQUEST:

{user_query}


============================================================
CORE RULE
============================================================

Separate:

1. KNOWLEDGE questions
2. OPERATIONAL data requirements
3. DETERMINISTIC calculations

Do not answer the user's question yourself.


============================================================
CONVERSATION RULES
============================================================

Use previous conversation context only when needed to
resolve references in the CURRENT request.

Example:

Previous answer:
"City Sights Tour and Sentosa Discovery Tour are feasible."

Current request:
"Tell me more about the second one."

Resolve:
"the second one"
→ Sentosa Discovery Tour

The CURRENT request has priority.

Do not automatically repeat every intent from the
previous turn.

Example:

Previous:
"Which tours can I join and do I need a visa?"

Current:
"Give me more detail about City Sights Tour."

The current request is only asking for FST knowledge.

Do NOT automatically repeat:
- visa lookup
- flight lookup
- transit calculation

unless they are actually required by the new question.


============================================================
KNOWLEDGE REQUESTS
============================================================

Create one KnowledgeRequest for each independent
knowledge domain needed.

Allowed topics:

visa
fst
customs


-------------------------
VISA
-------------------------
Use topic="visa" for all Singapore visa and immigration
entry-policy questions, including:

- whether a passport holder needs a visa
- Singapore entry visa requirements
- visa application procedures
- visa fees
- visa documents
- visa exemptions
- Visa Free Transit Facility (VFTF)
- VFTF eligibility and conditions

IMPORTANT:

The retrieval query should include the specific policy concepts
that may be needed to answer the user's question.

Example:

User:
"I am Chinese. Do I need to apply for a visa to enter Singapore?"

topic:
visa

query:
Singapore entry visa requirements for Chinese passport holders,
including relevant visa exemptions and Visa Free Transit Facility
(VFTF) conditions.


-------------------------
FST
-------------------------

Use topic="fst" for:

- Free Singapore Tour
- City Sights Tour
- Heritage and Culture Tour
- Sentosa Discovery Tour
- Singapore River and Marina Bay Sands Tour
- itinerary
- attractions
- tour details
- FST requirements
- registration rules
- participation policy


Examples:

"Give me more detail about City Sights Tour"

→ one knowledge request:

topic:
fst

query:
Give detailed information about City Sights Tour,
including its itinerary and attractions.


"What are the requirements for joining FST?"

→ one fst knowledge request.


-------------------------
CUSTOMS
-------------------------

Use topic="customs" for:

- controlled goods
- prohibited goods
- bringing goods into Singapore
- customs declarations
- drones
- cigarettes
- customs offences
- composition amounts
- permits


Example:

"Can I bring a drone into Singapore?"

→ one customs knowledge request.


============================================================
COMPOUND QUESTIONS
============================================================

A user request may create MULTIPLE knowledge requests.

Example:

"I'm an Indian passport holder.
Can I bring a drone into Singapore,
and can I join City Sights Tour?"

Possible knowledge requests:

1.
topic = visa
query = Singapore visa requirement for an Indian
passport holder.

2.
topic = customs
query = Rules for bringing a drone into Singapore.

3.
topic = fst
query = City Sights Tour details and participation
requirements.

If VFTF is relevant to the user's transit decision,
also create a separate vftf request.

Each retrieval query should be focused on ONE domain.

Preserve important entities such as:
- India
- City Sights Tour
- drone
- cigarettes
- VFTF


============================================================
OPERATIONAL TOOL ROUTING
============================================================

Set:

needs_arrival_flight_lookup = true

only when actual arrival flight operational data is
required.


Set:

needs_departure_flight_lookup = true

only when actual departure flight operational data is
required.


Set:

needs_transit_calculation = true

when arrival and departure times must be compared.


Set:

needs_fst_operational_check = true

ONLY when the user wants to know which actual FST
sessions are operationally feasible based on their
journey.


IMPORTANT DISTINCTION:

"Give me more detail about City Sights Tour"

→ knowledge_requests = [fst]
→ needs_arrival_flight_lookup = false
→ needs_departure_flight_lookup = false
→ needs_transit_calculation = false
→ needs_fst_operational_check = false


"Which FST can I join with SQ12 and SQ318?"

→ knowledge_requests includes fst
→ needs_arrival_flight_lookup = true
→ needs_departure_flight_lookup = true
→ needs_transit_calculation = true
→ needs_fst_operational_check = true


============================================================
DATES
============================================================

Output dates as:

YYYY-MM-DD

If the user provides month/day but no year, resolve the
next reasonable occurrence relative to the reference
date.

Example:

Reference date:
2026-08-09

"Aug 20"
→ 2026-08-20

Do not invent a date when none is provided.


============================================================
FLIGHT NUMBERS
============================================================

Normalize:

"sq 12"
→ SQ12

"Sq318"
→ SQ318


============================================================
MISSING INFORMATION
============================================================

Do not invent missing values.

If a knowledge question requires user-specific context
that is unavailable, include it in missing_fields.

Example:

"Do I need a Singapore visa?"

with no passport country in the current request or
conversation:

missing_fields:
["passport_country"]

Operational inputs are also validated by Python after
your output.

Return ONLY the structured TravelRequest.
""".strip()

        result = (
            self.structured_llm
            .invoke(
                prompt
            )
        )

        # =================================================
        # Normalise extracted values
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
                result.passport_country
                .strip()
            )

        # =================================================
        # Clean RAG plan
        # =================================================

        result.knowledge_requests = (
            self._normalize_knowledge_requests(
                result.knowledge_requests
            )
        )

        # =================================================
        # Enforce deterministic tool dependencies
        # =================================================

        self._apply_tool_dependencies(
            result
        )

        # =================================================
        # Validate missing operational inputs
        # =================================================

        result.missing_fields = (
            self._validate_missing_fields(
                result
            )
        )

        return result