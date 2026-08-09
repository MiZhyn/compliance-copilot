from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from src.database.fst_recommendation_service import (
    FSTEligibilityService,
)

from src.orchestration.planner import (
    TravelPlanner,
    TravelRequest,
)

from src.rag.answer_generator import (
    Evidence,
)

from src.rag.pipeline import (
    RAGPipeline,
)


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
# Response object
# =========================================================

@dataclass
class TravelCopilotResponse:
    """
    Final result returned by the Travel Copilot.

    Contains:
    - final natural-language answer
    - structured planner result
    - deterministic FST result
    - visa policy evidence
    - FST policy evidence
    """

    answer: str

    request: TravelRequest

    fst_result: Any | None

    visa_evidence: list[Evidence]

    fst_policy_evidence: list[Evidence]


# =========================================================
# Travel Copilot
# =========================================================

class TravelCopilot:
    """
    End-to-end travel and compliance orchestration layer.

    Responsibilities are deliberately separated:

    Planner
        -> understand user intent
        -> extract structured entities

    RAG
        -> retrieve authoritative policy evidence

    SQLite + Python
        -> retrieve operational facts
        -> perform deterministic calculations

    Claude
        -> synthesize and explain the final result
    """

    def __init__(
        self,
    ) -> None:

        print(
            "\n===================================="
        )

        print(
            "INITIALISING TRAVEL COPILOT"
        )

        print(
            "===================================="
        )

        # =================================================
        # 1. Planner
        # =================================================

        self.planner = (
            TravelPlanner()
        )

        # =================================================
        # 2. RAG policy layer
        # =================================================

        self.rag_pipeline = (
            RAGPipeline()
        )

        # =================================================
        # 3. Operational / deterministic layer
        # =================================================

        self.fst_service = (
            FSTEligibilityService()
        )

        # =================================================
        # 4. Final synthesis model
        # =================================================

        api_key = os.getenv(
            "ANTHROPIC_API_KEY"
        )

        if not api_key:

            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Please add it to the project .env file."
            )

        model_name = os.getenv(
            "ANTHROPIC_MODEL",
            DEFAULT_ANTHROPIC_MODEL,
        )

        print(
            f"Final synthesis model: "
            f"{model_name}"
        )

        self.llm = ChatAnthropic(
            model=model_name,
            temperature=0,
            max_tokens=2000,
        )


    # =====================================================
    # Missing field response
    # =====================================================

    def _build_missing_fields_answer(
        self,
        request: TravelRequest,
    ) -> str:
        """
        Do not allow the LLM to invent missing operational
        inputs.

        Return a deterministic clarification message.
        """

        fields = ", ".join(
            request.missing_fields
        )

        return (
            "I need some additional information "
            "before I can complete the requested checks. "
            f"Missing fields: {fields}."
        )


    # =====================================================
    # Build focused policy queries
    # =====================================================

    def _build_visa_policy_query(
        self,
        request: TravelRequest,
    ) -> str:
        """
        Build a focused retrieval query for visa /
        immigration policy.

        VFTF is included because this use case concerns
        transit passengers.
        """

        country = (
            request.passport_country
            or "the traveller"
        )

        return (
            f"For a {country} passport holder "
            f"transiting through Singapore, "
            f"what are the Singapore entry visa "
            f"requirements and what are the conditions "
            f"for using the Visa Free Transit Facility "
            f"(VFTF)?"
        )


    def _build_fst_policy_query(
        self,
    ) -> str:
        """
        Build a focused Free Singapore Tour policy query.
        """

        return (
            "What are the eligibility, registration, "
            "entry, visa, document, age, and participation "
            "requirements for joining the "
            "Free Singapore Tour?"
        )


    # =====================================================
    # Format policy evidence
    # =====================================================

    def _format_policy_evidence(
        self,
        evidence_list: list[Evidence],
        prefix: str,
    ) -> str:
        """
        Convert parent RAG evidence into source blocks
        for final synthesis.

        Example:

            [VISA1]
            [VISA2]

            [FST1]
            [FST2]
        """

        if not evidence_list:

            return ""

        blocks: list[str] = []

        for index, evidence in enumerate(
            evidence_list,
            start=1,
        ):

            document = (
                evidence.document
            )

            citation_id = (
                f"{prefix}{index}"
            )

            parts: list[str] = [
                f"[{citation_id}]",
                (
                    "Rerank score: "
                    f"{evidence.rerank_score}"
                ),
                (
                    "Source: "
                    f"{document.source}"
                ),
                (
                    "Title: "
                    f"{document.title}"
                ),
            ]

            if document.heading_path:

                parts.append(
                    "Heading: "
                    f"{document.heading_path}"
                )

            if document.url:

                parts.append(
                    "URL: "
                    f"{document.url}"
                )

            if document.page is not None:

                parts.append(
                    "Page: "
                    f"{document.page}"
                )

            parts.append(
                "Content:\n"
                f"{document.content}"
            )

            blocks.append(
                "\n".join(
                    parts
                )
            )

        return (
            "\n\n"
            "------------------------------------"
            "\n\n"
        ).join(
            blocks
        )


    # =====================================================
    # Format deterministic operational result
    # =====================================================

    def _format_operational_result(
        self,
        fst_result: Any | None,
    ) -> str:
        """
        Convert SQLite + deterministic Python results into
        evidence for final answer generation.

        Claude is allowed to explain these facts,
        but must not recalculate or override them.
        """

        if fst_result is None:

            return (
                "No operational FST check was requested."
            )

        arrival = (
            fst_result.arrival_flight
        )

        departure = (
            fst_result.departure_flight
        )

        arrival_datetime = (
            arrival.get(
                "estimated_datetime"
            )
            or arrival.get(
                "scheduled_datetime"
            )
        )

        departure_datetime = (
            departure.get(
                "estimated_datetime"
            )
            or departure.get(
                "scheduled_datetime"
            )
        )

        lines: list[str] = [
            "[OPS1]",
            (
                "Source: SQLite operational data "
                "+ deterministic Python calculation"
            ),
            "",
            "Arrival flight:",
            (
                f"- Flight: "
                f"{arrival.get('flight_number')}"
            ),
            (
                f"- Date: "
                f"{arrival.get('flight_date')}"
            ),
            (
                f"- Time: "
                f"{arrival_datetime}"
            ),
            (
                f"- Terminal: "
                f"{arrival.get('terminal')}"
            ),
            "",
            "Departure flight:",
            (
                f"- Flight: "
                f"{departure.get('flight_number')}"
            ),
            (
                f"- Date: "
                f"{departure.get('flight_date')}"
            ),
            (
                f"- Time: "
                f"{departure_datetime}"
            ),
            (
                f"- Terminal: "
                f"{departure.get('terminal')}"
            ),
            "",
            (
                "Calculated transit duration: "
                f"{fst_result.transit_hours} hours"
            ),
            "",
            "Operationally feasible FST sessions:",
        ]

        # =================================================
        # Eligible sessions
        # =================================================

        if not fst_result.eligible_sessions:

            lines.append(
                "- None"
            )

        else:

            for session in (
                fst_result.eligible_sessions
            ):

                lines.append(
                    (
                        f"- {session.tour_name}"
                    )
                )

                lines.append(
                    (
                        f"  Session: "
                        f"{session.session_code}"
                    )
                )

                lines.append(
                    (
                        f"  Start: "
                        f"{session.start_datetime}"
                    )
                )

                lines.append(
                    (
                        f"  End: "
                        f"{session.end_datetime}"
                    )
                )

                lines.append(
                    (
                        f"  Remaining slots: "
                        f"{session.remaining_slots}"
                    )
                )

        lines.extend(
            [
                "",
                (
                    "Important interpretation:"
                ),
                (
                    "These sessions are operationally "
                    "feasible based only on flight timing, "
                    "session timing, session status, "
                    "and remaining capacity."
                ),
                (
                    "This does NOT by itself confirm that "
                    "the traveller satisfies immigration "
                    "or Free Singapore Tour policy "
                    "requirements."
                ),
            ]
        )

        return "\n".join(
            lines
        )


    # =====================================================
    # Final synthesis
    # =====================================================

    def _synthesise(
        self,
        user_query: str,
        request: TravelRequest,
        fst_result: Any | None,
        visa_evidence: list[Evidence],
        fst_evidence: list[Evidence],
    ) -> str:
        """
        Combine:

        - planner output
        - SQL operational facts
        - deterministic Python results
        - visa RAG evidence
        - FST RAG evidence

        into one grounded answer.
        """

        # =================================================
        # Structured planner result
        # =================================================

        request_json = (
            request.model_dump_json(
                indent=2
            )
        )

        # =================================================
        # Operational facts
        # =================================================

        operational_text = (
            self._format_operational_result(
                fst_result
            )
        )

        # =================================================
        # Visa evidence
        # =================================================

        visa_text = (
            self._format_policy_evidence(
                evidence_list=(
                    visa_evidence
                ),
                prefix="VISA",
            )
        )

        # =================================================
        # FST evidence
        # =================================================

        fst_text = (
            self._format_policy_evidence(
                evidence_list=(
                    fst_evidence
                ),
                prefix="FST",
            )
        )

        prompt = f"""
You are the final response layer of an enterprise travel
and compliance copilot.

Your job is to synthesize information produced by
different trusted system components.

The information below may come from:

1. An LLM planner that extracted user intent
2. SQLite operational data
3. Deterministic Python calculations
4. Authoritative policy documents retrieved by RAG


USER QUESTION:

{user_query}


STRUCTURED USER REQUEST:

{request_json}


OPERATIONAL FACTS:

{operational_text}


VISA / IMMIGRATION POLICY EVIDENCE:

{visa_text if visa_text else "No visa evidence was requested."}


FREE SINGAPORE TOUR POLICY EVIDENCE:

{fst_text if fst_text else "No FST policy evidence was requested."}


GROUNDING RULES:

1. Use ONLY the information supplied above.

2. Do not use outside knowledge.

3. Do not perform new calculations.

4. Do not override deterministic operational results.

5. Cite flight times, transit duration, available
   sessions, and operational calculations using [OPS1].

6. Cite visa / immigration policy using the exact
   citation IDs:
   [VISA1], [VISA2], [VISA3], etc.

7. Cite Free Singapore Tour policy using:
   [FST1], [FST2], [FST3], etc.

8. Clearly distinguish between:

   - operationally feasible sessions
   - full policy eligibility

9. Do NOT say that a traveller is definitely eligible
   for a tour solely because the flight timing works.

10. If the traveller normally requires an entry visa
    but may qualify for VFTF, explain those as two
    separate concepts.

11. Do NOT state that the traveller qualifies for VFTF
    unless every required condition is supported by the
    supplied information.

12. If VFTF eligibility cannot be fully determined,
    state exactly which information is still missing.

13. Do not strengthen policy wording.

    For example:

    "may be eligible"
    must not become
    "is eligible"

14. Do not invent missing permits, visas, tickets,
    passport types, or travel conditions.

15. Keep the answer concise, practical, and easy to scan.


PREFERRED ANSWER STRUCTURE:

1. Short conclusion

2. Operationally feasible Free Singapore Tour options

3. Visa / VFTF status

4. Remaining conditions or information needed
""".strip()

        response = (
            self.llm.invoke(
                prompt
            )
        )

        content = (
            response.content
        )

        if isinstance(
            content,
            str,
        ):

            return content

        return str(
            content
        )


    # =====================================================
    # Main orchestration
    # =====================================================

    def run(
        self,
        user_query: str,
    ) -> TravelCopilotResponse:
        """
        Execute the complete workflow.
        """

        # =================================================
        # STEP 1
        # Planner
        # =================================================

        print(
            "\n[1/5] Planning request..."
        )

        request = (
            self.planner.plan(
                user_query
            )
        )

        print(
            request.model_dump_json(
                indent=2
            )
        )

        # =================================================
        # Missing required inputs
        # =================================================

        if request.missing_fields:

            answer = (
                self._build_missing_fields_answer(
                    request
                )
            )

            return TravelCopilotResponse(
                answer=answer,
                request=request,
                fst_result=None,
                visa_evidence=[],
                fst_policy_evidence=[],
            )

        # =================================================
        # STEP 2
        # Operational data + deterministic calculation
        # =================================================

        print(
            "\n[2/5] Checking operational data..."
        )

        fst_result = None

        if request.check_fst:

            fst_result = (
                self.fst_service.evaluate(
                    arrival_flight_number=(
                        request.arrival_flight
                    ),
                    arrival_date=(
                        request.arrival_date
                    ),
                    departure_flight_number=(
                        request.departure_flight
                    ),
                    departure_date=(
                        request.departure_date
                    ),
                )
            )

            print(
                "Transit hours: "
                f"{fst_result.transit_hours}"
            )

            print(
                "Operationally feasible sessions: "
                f"{len(fst_result.eligible_sessions)}"
            )

        else:

            print(
                "No FST operational check requested."
            )

        # =================================================
        # STEP 3
        # Visa / immigration RAG
        # =================================================

        print(
            "\n[3/5] Retrieving visa policy..."
        )

        visa_evidence: list[
            Evidence
        ] = []

        if request.check_visa:

            visa_query = (
                self._build_visa_policy_query(
                    request
                )
            )

            print(
                f"Visa retrieval query:\n"
                f"{visa_query}"
            )

            (
                visa_evidence,
                _,
            ) = (
                self.rag_pipeline
                .retrieve_evidence(
                    visa_query
                )
            )

            print(
                "Visa evidence documents: "
                f"{len(visa_evidence)}"
            )

        else:

            print(
                "No visa policy check requested."
            )

        # =================================================
        # STEP 4
        # FST policy RAG
        # =================================================

        print(
            "\n[4/5] Retrieving FST policy..."
        )

        fst_policy_evidence: list[
            Evidence
        ] = []

        if request.check_fst:

            fst_query = (
                self._build_fst_policy_query()
            )

            print(
                f"FST retrieval query:\n"
                f"{fst_query}"
            )

            (
                fst_policy_evidence,
                _,
            ) = (
                self.rag_pipeline
                .retrieve_evidence(
                    fst_query
                )
            )

            print(
                "FST policy evidence documents: "
                f"{len(fst_policy_evidence)}"
            )

        else:

            print(
                "No FST policy retrieval requested."
            )

        # =================================================
        # STEP 5
        # Final synthesis
        # =================================================

        print(
            "\n[5/5] Generating final answer..."
        )

        answer = (
            self._synthesise(
                user_query=user_query,
                request=request,
                fst_result=fst_result,
                visa_evidence=(
                    visa_evidence
                ),
                fst_evidence=(
                    fst_policy_evidence
                ),
            )
        )

        # =================================================
        # Return complete result
        # =================================================

        return TravelCopilotResponse(
            answer=answer,
            request=request,
            fst_result=fst_result,
            visa_evidence=(
                visa_evidence
            ),
            fst_policy_evidence=(
                fst_policy_evidence
            ),
        )