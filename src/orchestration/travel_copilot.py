# src/orchestration/travel_copilot.py

from __future__ import annotations

import os
import re

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urljoin

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from src.database.flight_repository import (
    FlightRepository,
)

from src.database.fst_recommendation_service import (
    FSTEligibilityService,
)

from src.orchestration.planner import (
    KnowledgeRequest,
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
# Environment
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


# Used by the Streamlit UI.
#
# The database stores demo operational availability.
# Actual booking is handed off to the official FST portal.
FST_BOOKING_URL = (
    "https://fst.changiairport.com/tour/"
)


# =========================================================
# Knowledge retrieval result
# =========================================================

@dataclass
class KnowledgeEvidenceGroup:
    """
    Evidence returned for one decomposed knowledge request.

    Example:

    topic = "customs"

    query =
        "Rules for bringing a drone into Singapore"

    evidence =
        [...]
    """

    topic: str

    query: str

    evidence: list[Evidence]


# =========================================================
# Prepared execution
# =========================================================

@dataclass
class PreparedTravelExecution:
    """
    Result after:

    - planning
    - SQL lookup
    - Python calculation
    - RAG retrieval

    but BEFORE the final Claude synthesis.

    This separation allows Streamlit to stream only
    the final answer.
    """

    user_query: str

    conversation_context: str | None

    request: TravelRequest

    fst_result: Any | None

    flight_facts: dict[
        str,
        dict,
    ]

    transit_hours: float | None

    knowledge_results: list[
        KnowledgeEvidenceGroup
    ]

    # Used when no LLM synthesis is necessary,
    # for example when required fields are missing.
    direct_answer: str | None = None


# =========================================================
# Final response
# =========================================================

@dataclass
class TravelCopilotResponse:
    """
    Complete response returned to non-streaming consumers
    and the Streamlit structured UI.
    """

    answer: str

    request: TravelRequest

    # -----------------------------------------------------
    # Operational results
    # -----------------------------------------------------

    fst_result: Any | None

    flight_facts: dict[
        str,
        dict,
    ]

    transit_hours: float | None

    # -----------------------------------------------------
    # Knowledge results
    # -----------------------------------------------------

    knowledge_results: list[
        KnowledgeEvidenceGroup
    ]


    # =====================================================
    # Compatibility helpers
    # =====================================================

    @property
    def visa_evidence(
        self,
    ) -> list[Evidence]:

        result: list[
            Evidence
        ] = []

        for group in (
            self.knowledge_results
        ):

            if group.topic == "visa":
                result.extend(
                    group.evidence
                )

        return result


    @property
    def fst_policy_evidence(
        self,
    ) -> list[Evidence]:

        result: list[
            Evidence
        ] = []

        for group in (
            self.knowledge_results
        ):

            if (
                group.topic
                == "fst"
            ):

                result.extend(
                    group.evidence
                )

        return result


    @property
    def customs_evidence(
        self,
    ) -> list[Evidence]:

        result: list[
            Evidence
        ] = []

        for group in (
            self.knowledge_results
        ):

            if (
                group.topic
                == "customs"
            ):

                result.extend(
                    group.evidence
                )

        return result


# =========================================================
# Travel Copilot
# =========================================================

class TravelCopilot:
    """
    Controlled orchestration layer.

    User Query
        ↓
    TravelPlanner
        ↓
    Query Decomposition
        ↓

    ┌──────────────────┬──────────────────┐
    │                  │                  │
    ↓                  ↓                  ↓
    RAG                SQL              Python
    policy             operational      deterministic
    knowledge          facts            logic
    │                  │                  │
    └──────────────────┴──────────────────┘
                       ↓
                 Prepared Result
                       ↓
              Claude Final Synthesis
                       ↓
                  User Response


    Core design:

    LLM
        understanding / planning / explanation

    RAG
        policy knowledge

    SQL
        operational facts

    Python
        deterministic calculations
    """

    def __init__(
        self,
    ) -> None:

        print(
            "\n======================================"
        )

        print(
            "INITIALISING TRAVEL COPILOT"
        )

        print(
            "======================================"
        )


        # =================================================
        # Planner
        # =================================================

        self.planner = (
            TravelPlanner()
        )


        # =================================================
        # RAG
        #
        # This is intentionally constructed only once when
        # TravelCopilot itself is cached by Streamlit.
        #
        # RAGPipeline may initialise:
        # - BGE embedding model
        # - Chroma
        # - BM25
        # - parent store
        # - reranker
        # =================================================

        self.rag_pipeline = (
            RAGPipeline()
        )


        # =================================================
        # Operational tools
        # =================================================

        self.flight_repository = (
            FlightRepository()
        )

        self.fst_service = (
            FSTEligibilityService()
        )


        # =================================================
        # Final synthesis model
        # =================================================

        api_key = os.getenv(
            "ANTHROPIC_API_KEY"
        )

        if not api_key:

            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set."
            )


        model_name = os.getenv(
            "ANTHROPIC_MODEL",
            DEFAULT_ANTHROPIC_MODEL,
        )


        print(
            "Final synthesis model: "
            f"{model_name}"
        )


        self.llm = ChatAnthropic(
            model=model_name,
            temperature=0,
            max_tokens=2200,
        )


    # =====================================================
    # Missing information
    # =====================================================

    @staticmethod
    def _build_missing_fields_answer(
        request: TravelRequest,
    ) -> str:

        labels = {
            "passport_country":
                "passport / nationality",

            "arrival_flight":
                "arrival flight number",

            "arrival_date":
                "arrival date",

            "departure_flight":
                "departure flight number",

            "departure_date":
                "departure date",
        }


        readable_fields = [
            labels.get(
                field,
                field.replace(
                    "_",
                    " ",
                ),
            )
            for field
            in request.missing_fields
        ]


        items = "\n".join(
            f"- {field}"
            for field
            in readable_fields
        )


        return (
            "I need a little more information "
            "before I can complete this check:\n\n"
            f"{items}"
        )


    # =====================================================
    # Trusted document links
    # =====================================================

    @staticmethod
    def _extract_document_links(
        document,
    ) -> list[
        tuple[str, str]
    ]:
        """
        Extract URLs that already exist inside a retrieved
        CanonicalDocument.

        Important:
        URLs are grounded in source data.

        Claude is NOT allowed to invent URLs.
        """

        links: list[
            tuple[str, str]
        ] = []

        seen_urls: set[
            str
        ] = set()


        base_url = getattr(
            document,
            "url",
            None,
        )


        # =================================================
        # URL normalisation
        # =================================================

        def normalize_url(
            value: str,
        ) -> str | None:

            value = (
                value
                .strip()
                .rstrip(
                    ".,;"
                )
            )


            if not value:

                return None


            if value.startswith(
                (
                    "https://",
                    "http://",
                )
            ):

                return value


            # Relative URL from a webpage.
            if (
                base_url
                and value.startswith("/")
            ):

                return urljoin(
                    base_url,
                    value,
                )


            return None


        # =================================================
        # Add unique URL
        # =================================================

        def add_link(
            label: str,
            url: str,
        ) -> None:

            clean_url = (
                normalize_url(
                    url
                )
            )


            if not clean_url:

                return


            if (
                clean_url
                in seen_urls
            ):

                return


            seen_urls.add(
                clean_url
            )


            clean_label = (
                " ".join(
                    str(label)
                    .split()
                )
                or "Official resource"
            )


            links.append(
                (
                    clean_label,
                    clean_url,
                )
            )


        # =================================================
        # Source page
        # =================================================

        if base_url:

            add_link(
                "Official source page",
                base_url,
            )


        # =================================================
        # Patterns
        # =================================================

        markdown_link_pattern = (
            re.compile(
                r"\[([^\]]+)\]"
                r"\((https?://[^)]+)\)"
            )
        )


        html_link_pattern = (
            re.compile(
                r'<a[^>]+href=["\']'
                r'([^"\']+)["\'][^>]*>'
                r'(.*?)</a>',
                re.IGNORECASE
                | re.DOTALL,
            )
        )


        raw_url_pattern = (
            re.compile(
                r"https?://"
                r"[^\s<>\]\)\"']+"
            )
        )


        # =================================================
        # String parser
        # =================================================

        def parse_string(
            value: str,
            label_hint: str,
        ) -> None:

            # ---------------------------------------------
            # Markdown links
            # ---------------------------------------------

            for (
                label,
                url,
            ) in (
                markdown_link_pattern
                .findall(
                    value
                )
            ):

                add_link(
                    label,
                    url,
                )


            # ---------------------------------------------
            # HTML links
            # ---------------------------------------------

            for (
                url,
                label,
            ) in (
                html_link_pattern
                .findall(
                    value
                )
            ):

                clean_label = (
                    re.sub(
                        r"<[^>]+>",
                        "",
                        label,
                    )
                    .strip()
                )


                add_link(
                    clean_label
                    or label_hint,
                    url,
                )


            # ---------------------------------------------
            # Raw URLs
            # ---------------------------------------------

            for url in (
                raw_url_pattern
                .findall(
                    value
                )
            ):

                add_link(
                    label_hint,
                    url,
                )


        # =================================================
        # Recursive metadata walker
        # =================================================

        def walk(
            value,
            label_hint: str = (
                "Official resource"
            ),
        ) -> None:

            # ---------------------------------------------
            # String
            # ---------------------------------------------

            if isinstance(
                value,
                str,
            ):

                parse_string(
                    value,
                    label_hint,
                )

                return


            # ---------------------------------------------
            # List
            # ---------------------------------------------

            if isinstance(
                value,
                list,
            ):

                for item in value:

                    walk(
                        item,
                        label_hint,
                    )

                return


            # ---------------------------------------------
            # Dictionary
            # ---------------------------------------------

            if isinstance(
                value,
                dict,
            ):

                direct_url = (
                    value.get("url")
                    or value.get("href")
                    or value.get("link")
                )


                direct_label = (
                    value.get("text")
                    or value.get("label")
                    or value.get("title")
                    or value.get("name")
                    or label_hint
                )


                if isinstance(
                    direct_url,
                    str,
                ):

                    add_link(
                        str(
                            direct_label
                        ),
                        direct_url,
                    )


                for (
                    key,
                    child,
                ) in value.items():

                    if key in {
                        "url",
                        "href",
                        "link",
                    }:

                        continue


                    walk(
                        child,
                        str(key),
                    )


        # =================================================
        # Inspect metadata
        # =================================================

        metadata = getattr(
            document,
            "metadata",
            {},
        )


        walk(
            metadata
        )


        # =================================================
        # Inspect document content
        # =================================================

        content = getattr(
            document,
            "content",
            "",
        )


        if content:

            parse_string(
                content,
                "Official resource",
            )


        return links


    # =====================================================
    # Knowledge retrieval
    # =====================================================

    def _retrieve_knowledge(
        self,
        requests: list[
            KnowledgeRequest
        ],
    ) -> list[
        KnowledgeEvidenceGroup
    ]:
        """
        Run each decomposed topic as an independent RAG
        retrieval task.

        Example compound question:

        visa
            → own retrieval

        customs
            → own retrieval

        fst
            → own retrieval

        This prevents unrelated topics competing for one
        shared Top-K budget.
        """

        groups: list[
            KnowledgeEvidenceGroup
        ] = []


        total = len(
            requests
        )


        for (
            index,
            item,
        ) in enumerate(
            requests,
            start=1,
        ):

            print(
                "\n--------------------------------------"
            )

            print(
                "KNOWLEDGE RETRIEVAL "
                f"{index}/{total}"
            )

            print(
                f"Topic: {item.topic}"
            )

            print(
                f"Query: {item.query}"
            )


            (
                evidence,
                _,
            ) = (
                self.rag_pipeline
                .retrieve_evidence(
                    query=item.query
                )
            )


            print(
                "Evidence documents: "
                f"{len(evidence)}"
            )


            groups.append(
                KnowledgeEvidenceGroup(
                    topic=item.topic,
                    query=item.query,
                    evidence=evidence,
                )
            )


        return groups


    # =====================================================
    # Flight lookup
    # =====================================================

    def _lookup_flight(
        self,
        flight_number: str,
        flight_date: str,
        direction: str,
    ) -> dict:

        flight = (
            self.flight_repository
            .get_flight(
                flight_number=(
                    flight_number
                ),
                flight_date=(
                    flight_date
                ),
                direction=direction,
            )
        )


        if flight is None:

            raise ValueError(
                "Flight not found: "
                f"{flight_number} "
                f"on {flight_date}"
            )


        return flight


    # =====================================================
    # Effective datetime
    # =====================================================

    @staticmethod
    def _get_effective_datetime(
        flight: dict,
    ) -> datetime:

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
                "Flight record does not contain "
                "a usable datetime."
            )


        return datetime.strptime(
            value,
            "%Y-%m-%d %H:%M:%S",
        )


    # =====================================================
    # Transit calculation
    # =====================================================

    @classmethod
    def _calculate_transit_hours(
        cls,
        arrival: dict,
        departure: dict,
    ) -> float:

        arrival_time = (
            cls._get_effective_datetime(
                arrival
            )
        )


        departure_time = (
            cls._get_effective_datetime(
                departure
            )
        )


        seconds = (
            departure_time
            - arrival_time
        ).total_seconds()


        if seconds < 0:

            raise ValueError(
                "Departure time occurs before "
                "arrival time."
            )


        return round(
            seconds / 3600,
            2,
        )


    # =====================================================
    # Operational tools
    # =====================================================

    def _execute_operational_tools(
        self,
        request: TravelRequest,
    ) -> tuple[
        Any | None,
        dict[str, dict],
        float | None,
    ]:
        """
        Execute SQL and deterministic Python logic.

        Full FST operational check is handled by
        FSTEligibilityService to avoid duplicate database
        lookups and duplicate calculation logic.
        """

        fst_result = None


        flight_facts: dict[
            str,
            dict
        ] = {}


        transit_hours = None


        # =================================================
        # Full FST operational check
        # =================================================

        if (
            request
            .needs_fst_operational_check
        ):

            print(
                "\nRunning FST operational check..."
            )


            fst_result = (
                self.fst_service
                .evaluate(
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


            flight_facts[
                "arrival"
            ] = (
                fst_result
                .arrival_flight
            )


            flight_facts[
                "departure"
            ] = (
                fst_result
                .departure_flight
            )


            transit_hours = (
                fst_result
                .transit_hours
            )


            print(
                "Transit hours: "
                f"{transit_hours}"
            )


            print(
                "Operationally feasible sessions: "
                f"{len(fst_result.eligible_sessions)}"
            )


            return (
                fst_result,
                flight_facts,
                transit_hours,
            )


        # =================================================
        # Arrival lookup
        # =================================================

        if (
            request
            .needs_arrival_flight_lookup
        ):

            flight_facts[
                "arrival"
            ] = (
                self._lookup_flight(
                    flight_number=(
                        request.arrival_flight
                    ),
                    flight_date=(
                        request.arrival_date
                    ),
                    direction="ARRIVAL",
                )
            )


        # =================================================
        # Departure lookup
        # =================================================

        if (
            request
            .needs_departure_flight_lookup
        ):

            flight_facts[
                "departure"
            ] = (
                self._lookup_flight(
                    flight_number=(
                        request.departure_flight
                    ),
                    flight_date=(
                        request.departure_date
                    ),
                    direction="DEPARTURE",
                )
            )


        # =================================================
        # Transit calculation
        # =================================================

        if (
            request
            .needs_transit_calculation
        ):

            arrival = (
                flight_facts.get(
                    "arrival"
                )
            )


            departure = (
                flight_facts.get(
                    "departure"
                )
            )


            if (
                arrival is None
                or departure is None
            ):

                raise ValueError(
                    "Transit calculation requires "
                    "both arrival and departure flights."
                )


            transit_hours = (
                self
                ._calculate_transit_hours(
                    arrival=arrival,
                    departure=departure,
                )
            )


        return (
            fst_result,
            flight_facts,
            transit_hours,
        )


    # =====================================================
    # Knowledge evidence formatting
    # =====================================================

    def _format_knowledge_evidence(
        self,
        groups: list[
            KnowledgeEvidenceGroup
        ],
    ) -> str:

        if not groups:

            return (
                "No policy knowledge retrieval "
                "was required."
            )


        prefixes = {
            "visa":
                "VISA",

            "fst":
                "FST",

            "customs":
                "CUSTOMS",
        }


        counters = {
            topic: 0
            for topic in prefixes
        }


        blocks: list[
            str
        ] = []


        for group in groups:

            blocks.append(
                (
                    "====================================\n"
                    f"Knowledge topic: "
                    f"{group.topic}\n"
                    f"Focused retrieval query: "
                    f"{group.query}\n"
                    "===================================="
                )
            )


            for evidence in (
                group.evidence
            ):

                counters[
                    group.topic
                ] += 1


                citation_id = (
                    f"{prefixes[group.topic]}"
                    f"{counters[group.topic]}"
                )


                document = (
                    evidence.document
                )


                parts: list[
                    str
                ] = [
                    f"[{citation_id}]",
                    (
                        "Source: "
                        f"{document.source}"
                    ),
                    (
                        "Title: "
                        f"{document.title}"
                    ),
                    (
                        "Rerank score: "
                        f"{evidence.rerank_score}"
                    ),
                ]


                if (
                    document
                    .heading_path
                ):

                    parts.append(
                        "Heading: "
                        f"{document.heading_path}"
                    )


                if (
                    document.page
                    is not None
                ):

                    parts.append(
                        "Page: "
                        f"{document.page}"
                    )


                parts.append(
                    "Content:\n"
                    f"{document.content}"
                )


                # =========================================
                # Trusted source URLs
                # =========================================

                links = (
                    self
                    ._extract_document_links(
                        document
                    )
                )


                if links:

                    parts.append(
                        (
                            "Trusted links supplied "
                            "by the source:"
                        )
                    )


                    for (
                        label,
                        url,
                    ) in links:

                        parts.append(
                            f"- {label}: {url}"
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
    # Operational context formatting
    # =====================================================

    @staticmethod
    def _format_operational_context(
        fst_result: Any | None,
        flight_facts: dict[
            str,
            dict,
        ],
        transit_hours: float | None,
    ) -> str:
        """
        Operational context for Claude.

        Important:
        Streamlit renders detailed journey and FST
        availability separately.

        Claude should explain the conclusion,
        not duplicate the structured UI.
        """

        if (
            fst_result is None
            and not flight_facts
            and transit_hours is None
        ):

            return (
                "No operational database lookup or "
                "deterministic calculation was required."
            )


        lines: list[
            str
        ] = [
            "[OPS1]",
            (
                "Source: operational SQLite data "
                "+ deterministic Python logic"
            ),
        ]


        # =================================================
        # Arrival
        # =================================================

        arrival = (
            flight_facts.get(
                "arrival"
            )
        )


        if arrival:

            arrival_time = (
                arrival.get(
                    "estimated_datetime"
                )
                or arrival.get(
                    "scheduled_datetime"
                )
            )


            lines.extend(
                [
                    "",
                    "Arrival flight:",
                    (
                        "- Flight: "
                        f"{arrival.get('flight_number')}"
                    ),
                    (
                        "- Date/time: "
                        f"{arrival_time}"
                    ),
                    (
                        "- Terminal: "
                        f"{arrival.get('terminal')}"
                    ),
                ]
            )


        # =================================================
        # Departure
        # =================================================

        departure = (
            flight_facts.get(
                "departure"
            )
        )


        if departure:

            departure_time = (
                departure.get(
                    "estimated_datetime"
                )
                or departure.get(
                    "scheduled_datetime"
                )
            )


            lines.extend(
                [
                    "",
                    "Departure flight:",
                    (
                        "- Flight: "
                        f"{departure.get('flight_number')}"
                    ),
                    (
                        "- Date/time: "
                        f"{departure_time}"
                    ),
                    (
                        "- Terminal: "
                        f"{departure.get('terminal')}"
                    ),
                ]
            )


        # =================================================
        # Transit
        # =================================================

        if (
            transit_hours
            is not None
        ):

            lines.extend(
                [
                    "",
                    (
                        "Calculated transit duration: "
                        f"{transit_hours} hours"
                    ),
                ]
            )


        # =================================================
        # FST
        # =================================================

        if (
            fst_result
            is not None
        ):

            sessions = (
                fst_result
                .eligible_sessions
            )


            lines.extend(
                [
                    "",
                    (
                        "Operationally feasible "
                        "Free Singapore Tour session count: "
                        f"{len(sessions)}"
                    ),
                ]
            )


            # These details remain available to Claude for
            # grounding, but Claude is instructed not to
            # repeat them in the prose response.

            for session in sessions:

                session_date = (
                    session
                    .start_datetime
                    .split(" ")[0]
                )


                lines.extend(
                    [
                        "",
                        (
                            "Tour: "
                            f"{session.tour_name}"
                        ),
                        (
                            "Date: "
                            f"{session_date}"
                        ),
                        (
                            "Start: "
                            f"{session.start_datetime}"
                        ),
                        (
                            "End: "
                            f"{session.end_datetime}"
                        ),
                        (
                            "Remaining slots: "
                            f"{session.remaining_slots}"
                        ),
                    ]
                )


            lines.extend(
                [
                    "",
                    (
                        "Important: operational feasibility "
                        "does not by itself confirm policy "
                        "or immigration eligibility."
                    ),
                    (
                        "Detailed journey and FST session "
                        "information is rendered separately "
                        "by the application UI."
                    ),
                ]
            )


        return "\n".join(
            lines
        )


    # =====================================================
    # Build final synthesis prompt
    # =====================================================

    def _build_synthesis_prompt(
        self,
        prepared: PreparedTravelExecution,
    ) -> str:
        """
        Build the exact same synthesis prompt used by:

        - normal invoke()
        - streaming stream()

        This ensures CLI and Streamlit produce responses
        using the same grounding rules.
        """

        structured_request = (
            prepared
            .request
            .model_dump_json(
                indent=2
            )
        )


        operational_text = (
            self
            ._format_operational_context(
                fst_result=(
                    prepared.fst_result
                ),
                flight_facts=(
                    prepared.flight_facts
                ),
                transit_hours=(
                    prepared.transit_hours
                ),
            )
        )


        knowledge_text = (
            self
            ._format_knowledge_evidence(
                prepared
                .knowledge_results
            )
        )


        context_text = (
            prepared
            .conversation_context
            or "No previous conversation."
        )


        return f"""
You are the final response layer of an enterprise
Travel & Compliance Copilot.

Planning, retrieval, database lookup and deterministic
calculations have already been completed.

Your job is ONLY to synthesise the supplied evidence.


CURRENT USER QUESTION:

{prepared.user_query}


PREVIOUS CONVERSATION:

{context_text}


STRUCTURED EXECUTION PLAN:

{structured_request}


OPERATIONAL FACTS:

{operational_text}


RETRIEVED KNOWLEDGE:

{knowledge_text}


============================================================
GROUNDING RULES
============================================================

1. Use only the evidence and operational facts supplied
   above.

2. Do not use outside knowledge.

3. Do not perform new calculations.

4. Do not override deterministic operational results.

5. Use [OPS1] for operational facts such as:

   - flight timing
   - terminals
   - transit duration
   - FST operational feasibility

6. Use the exact policy citation IDs supplied above:

   [VISA1]
   [FST1]
   [CUSTOMS1]

   etc.

7. Cite factual policy conclusions.

8. Treat separate knowledge topics independently.

9. Combine topics only when required to answer the
   overall user question.

10. Operational feasibility does NOT automatically prove
    immigration or policy eligibility.

11. Preserve uncertainty exactly.

    "may qualify"

    must not become:

    "qualifies"

12. If the supplied evidence is incomplete, clearly state
    what cannot be determined.

13. Previous conversation is contextual information only.

    It is NOT an authoritative policy source.


============================================================
ACTIONABLE LINKS
============================================================

14. Trusted URLs may appear under:

    "Trusted links supplied by the source"

15. You may ONLY use URLs explicitly supplied there.

16. Never invent, guess, modify, shorten or construct URLs.

17. When a trusted URL directly supports a useful action,
    render it using Markdown.

Examples:

[Check visa requirements](URL)

[Submit the application](URL)

[Open the official form](URL)

[Check permit requirements](URL)

18. Prefer meaningful action text rather than showing
    a long raw URL.


============================================================
STREAMLIT PRESENTATION
============================================================

19. The application renders structured operational
    information separately from this prose answer.

20. Journey information is displayed separately.

    Mention flight or transit information only when it
    materially supports the conclusion.

21. When operationally feasible FST sessions exist:

    - state the number of feasible sessions
    - state the overall conclusion
    - tell the user the options are shown below

22. Do NOT enumerate individual FST operational sessions.

23. Do NOT repeat:

    - individual FST tour names
    - dates
    - start/end times
    - remaining slot counts
    - internal session IDs
    - booking URLs

24. Do NOT create an FST operational session table.

25. The application renders the FST booking action
    separately as a "Book now" button.

26. For a general informational FST question where no
    operational session lookup occurred, you MAY explain:

    - tour details
    - itinerary
    - attractions
    - registration
    - participation requirements

    normally from the FST evidence.


============================================================
FOLLOW-UP QUESTIONS
============================================================

27. Use previous conversation only when necessary to
    resolve references such as:

    "the second one"

    "that tour"

    "what about the visa?"

28. Focus primarily on the CURRENT user question.

29. Do not automatically repeat every topic discussed
    in previous turns.


============================================================
ANSWER STYLE
============================================================

30. Start with the direct answer.

31. Prioritise:

    - conclusion
    - important policy conditions
    - missing information
    - practical next action

32. Use short headings when several topics are involved.

33. Avoid repeating structured operational information
    already presented by the UI.

34. Keep the response concise and user-friendly.

35. Do not expose internal chain-of-thought.

36. Do not explain the technical architecture unless the
    user explicitly asks about it.
""".strip()


    # =====================================================
    # Normal response → text
    # =====================================================

    @staticmethod
    def _response_to_text(
        response,
    ) -> str:

        content = (
            response.content
        )


        # =================================================
        # Plain string
        # =================================================

        if isinstance(
            content,
            str,
        ):

            return (
                content
                .strip()
            )


        # =================================================
        # Content blocks
        # =================================================

        if isinstance(
            content,
            list,
        ):

            text_parts: list[
                str
            ] = []


            for block in content:

                # -----------------------------------------
                # Dictionary content block
                # -----------------------------------------

                if isinstance(
                    block,
                    dict,
                ):

                    if (
                        block.get("type")
                        == "text"
                    ):

                        text = (
                            block.get(
                                "text"
                            )
                        )


                        if text:

                            text_parts.append(
                                str(text)
                            )


                    continue


                # -----------------------------------------
                # Object content block
                # -----------------------------------------

                text = getattr(
                    block,
                    "text",
                    None,
                )


                if text:

                    text_parts.append(
                        str(text)
                    )


            if text_parts:

                return (
                    "".join(
                        text_parts
                    )
                    .strip()
                )


        return (
            str(content)
            .strip()
        )


    # =====================================================
    # Streaming chunk → text
    # =====================================================

    @staticmethod
    def _stream_chunk_to_text(
        chunk,
    ) -> str:
        """
        Extract only visible answer text from a
        ChatAnthropic streaming chunk.

        ChatAnthropic exposes text on message chunks;
        this helper also handles content-block structures
        defensively.
        """

        # =================================================
        # Preferred ChatAnthropic convenience property
        # =================================================

        text = getattr(
            chunk,
            "text",
            None,
        )


        if isinstance(
            text,
            str,
        ) and text:

            return text


        # =================================================
        # Fallback to chunk.content
        # =================================================

        content = getattr(
            chunk,
            "content",
            None,
        )


        if isinstance(
            content,
            str,
        ):

            return content


        if isinstance(
            content,
            list,
        ):

            text_parts: list[
                str
            ] = []


            for block in content:

                if isinstance(
                    block,
                    dict,
                ):

                    if (
                        block.get("type")
                        == "text"
                    ):

                        block_text = (
                            block.get(
                                "text"
                            )
                        )


                        if block_text:

                            text_parts.append(
                                str(
                                    block_text
                                )
                            )


            return "".join(
                text_parts
            )


        return ""


    # =====================================================
    # PREPARE
    # Planner + SQL + Python + RAG
    # =====================================================

    def prepare(
        self,
        user_query: str,
        conversation_context: str | None = None,
    ) -> PreparedTravelExecution:
        """
        Run all work required BEFORE final synthesis.

        This method is used by Streamlit so the application
        can:

        1. show progress while tools are running
        2. then stream only the final Claude answer
        """

        # =================================================
        # STEP 1
        # Planner
        # =================================================

        print(
            "\n[1/3] Planning request..."
        )


        request = (
            self.planner
            .plan(
                user_query=(
                    user_query
                ),
                conversation_context=(
                    conversation_context
                ),
            )
        )


        print(
            request
            .model_dump_json(
                indent=2
            )
        )


        # =================================================
        # Missing information
        # =================================================

        if (
            request
            .missing_fields
        ):

            return (
                PreparedTravelExecution(
                    user_query=(
                        user_query
                    ),
                    conversation_context=(
                        conversation_context
                    ),
                    request=request,
                    fst_result=None,
                    flight_facts={},
                    transit_hours=None,
                    knowledge_results=[],
                    direct_answer=(
                        self
                        ._build_missing_fields_answer(
                            request
                        )
                    ),
                )
            )


        # =================================================
        # STEP 2
        # SQL / Python
        # =================================================

        print(
            "\n[2/3] Executing operational tools..."
        )


        (
            fst_result,
            flight_facts,
            transit_hours,
        ) = (
            self
            ._execute_operational_tools(
                request
            )
        )


        if (
            fst_result is None
            and not flight_facts
            and transit_hours is None
        ):

            print(
                "No SQL / Python tools required."
            )


        # =================================================
        # STEP 3
        # RAG
        # =================================================

        print(
            "\n[3/3] Retrieving knowledge..."
        )


        knowledge_results = (
            self
            ._retrieve_knowledge(
                request
                .knowledge_requests
            )
        )


        if not knowledge_results:

            print(
                "No RAG retrieval required."
            )


        # =================================================
        # Nothing routed
        # =================================================

        if (
            not knowledge_results
            and fst_result is None
            and not flight_facts
            and transit_hours is None
        ):

            return (
                PreparedTravelExecution(
                    user_query=(
                        user_query
                    ),
                    conversation_context=(
                        conversation_context
                    ),
                    request=request,
                    fst_result=None,
                    flight_facts={},
                    transit_hours=None,
                    knowledge_results=[],
                    direct_answer=(
                        "I could not identify a travel, "
                        "compliance, policy, or operational "
                        "check required for this request."
                    ),
                )
            )


        # =================================================
        # Prepared for final synthesis
        # =================================================

        return (
            PreparedTravelExecution(
                user_query=(
                    user_query
                ),
                conversation_context=(
                    conversation_context
                ),
                request=request,
                fst_result=(
                    fst_result
                ),
                flight_facts=(
                    flight_facts
                ),
                transit_hours=(
                    transit_hours
                ),
                knowledge_results=(
                    knowledge_results
                ),
                direct_answer=None,
            )
        )


    # =====================================================
    # STREAM final answer
    # =====================================================

    def stream_answer(
        self,
        prepared: PreparedTravelExecution,
    ) -> Iterator[str]:
        """
        Stream only the final Claude synthesis.

        Planner / SQL / Python / RAG already completed
        during prepare().

        This is intended for:

            st.write_stream(
                copilot.stream_answer(prepared)
            )
        """

        # =================================================
        # Direct response
        # =================================================

        if (
            prepared
            .direct_answer
        ):

            yield (
                prepared
                .direct_answer
            )

            return


        # =================================================
        # Build grounded synthesis prompt
        # =================================================

        prompt = (
            self
            ._build_synthesis_prompt(
                prepared
            )
        )


        # =================================================
        # Claude token streaming
        # =================================================

        for chunk in (
            self.llm
            .stream(
                prompt
            )
        ):

            text = (
                self
                ._stream_chunk_to_text(
                    chunk
                )
            )


            if text:

                yield text


    # =====================================================
    # Build normal response object
    # =====================================================

    @staticmethod
    def build_response(
        prepared: PreparedTravelExecution,
        answer: str,
    ) -> TravelCopilotResponse:
        """
        Convert a prepared execution + generated answer
        into the normal TravelCopilotResponse object.

        Useful after st.write_stream().
        """

        return (
            TravelCopilotResponse(
                answer=answer,
                request=(
                    prepared.request
                ),
                fst_result=(
                    prepared.fst_result
                ),
                flight_facts=(
                    prepared.flight_facts
                ),
                transit_hours=(
                    prepared.transit_hours
                ),
                knowledge_results=(
                    prepared
                    .knowledge_results
                ),
            )
        )


    # =====================================================
    # Non-streaming final synthesis
    # =====================================================

    def _synthesise(
        self,
        prepared: PreparedTravelExecution,
    ) -> str:
        """
        Standard non-streaming generation.

        Kept for:
        - CLI testing
        - unit/integration tests
        - code paths that do not use Streamlit
        """

        if (
            prepared
            .direct_answer
        ):

            return (
                prepared
                .direct_answer
            )


        prompt = (
            self
            ._build_synthesis_prompt(
                prepared
            )
        )


        response = (
            self.llm
            .invoke(
                prompt
            )
        )


        return (
            self
            ._response_to_text(
                response
            )
        )


    # =====================================================
    # Backwards-compatible RUN
    # =====================================================

    def run(
        self,
        user_query: str,
        conversation_context: str | None = None,
    ) -> TravelCopilotResponse:
        """
        Original one-call API.

        Existing tests can continue using:

            result = copilot.run(query)

        Streamlit should instead use:

            prepared = copilot.prepare(...)
            answer = st.write_stream(
                copilot.stream_answer(prepared)
            )
            result = copilot.build_response(
                prepared,
                answer,
            )
        """

        # =================================================
        # Prepare
        # =================================================

        prepared = (
            self.prepare(
                user_query=(
                    user_query
                ),
                conversation_context=(
                    conversation_context
                ),
            )
        )


        # =================================================
        # Generate
        # =================================================

        print(
            "\n[4/4] Generating grounded answer..."
        )


        answer = (
            self
            ._synthesise(
                prepared
            )
        )


        # =================================================
        # Return standard response
        # =================================================

        return (
            self
            .build_response(
                prepared=(
                    prepared
                ),
                answer=(
                    answer
                ),
            )
        )