from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from src.retrieval.hybrid_retriever import (
    HybridResult,
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
# Structured output from Claude
# =========================================================

class CandidateScore(BaseModel):
    """
    Claude's assessment of one retrieval candidate.
    """

    chunk_id: str = Field(
        description=(
            "The exact chunk ID supplied in the candidate."
        )
    )

    relevance_score: int = Field(
        description=(
            "Relevance score from 0 to 100. "
            "100 means the candidate directly answers "
            "the user's question."
        )
    )

    reason: str = Field(
        description=(
            "A short explanation of why this candidate "
            "is or is not relevant."
        )
    )


class RerankResponse(BaseModel):
    """
    Structured response containing every candidate.
    """

    results: list[CandidateScore]


# =========================================================
# Final result object
# =========================================================

@dataclass
class RerankedResult:
    """
    Hybrid retrieval result after Claude reranking.
    """

    hybrid_result: HybridResult

    rerank_score: int

    rerank_reason: str


# =========================================================
# Claude Reranker
# =========================================================

class ClaudeReranker:
    """
    Rerank Hybrid Retrieval candidates using Claude.

    Important:

    Claude is NOT searching the full corpus.

    It only sees the small candidate set already
    retrieved by Vector + BM25 + RRF.
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
            f"Reranker model: "
            f"{model_name}"
        )

        self.llm = ChatAnthropic(
            model=model_name,

            temperature=0,

            max_tokens=2500,
        )

        # Structured output makes parsing safer than
        # asking Claude to return free-form JSON.
        self.structured_llm = (
            self.llm.with_structured_output(
                RerankResponse,
                method="json_schema",
            )
        )


    # =====================================================
    # Prompt construction
    # =====================================================

    def _build_candidate_text(
        self,
        candidates: list[
            HybridResult
        ],
    ) -> str:
        """
        Convert HybridResult objects into a compact text
        representation for Claude.
        """

        sections: list[str] = []

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):

            document = (
                candidate.document
            )

            metadata = (
                document.metadata
            )

            chunk_id = str(
                metadata.get(
                    "chunk_id",
                    "",
                )
            )

            title = str(
                metadata.get(
                    "title",
                    "",
                )
            )

            heading = str(
                metadata.get(
                    "heading_path",
                    "",
                )
            )

            source = str(
                metadata.get(
                    "source",
                    "",
                )
            )

            section = f"""
CANDIDATE {index}

chunk_id:
{chunk_id}

source:
{source}

title:
{title}

heading:
{heading}

content:
{document.page_content}
""".strip()

            sections.append(
                section
            )

        return "\n\n---\n\n".join(
            sections
        )


    # =====================================================
    # Reranking
    # =====================================================

    def rerank(
        self,
        query: str,
        candidates: list[
            HybridResult
        ],
        final_k: int = 5,
    ) -> list[RerankedResult]:
        """
        Ask Claude to score query-document relevance.

        The final order is determined by Claude's
        relevance score.

        Hybrid score is kept for diagnostics but is
        not mixed mathematically with the rerank score.
        """

        if not candidates:

            return []

        candidate_text = (
            self._build_candidate_text(
                candidates
            )
        )

        prompt = f"""
You are a retrieval reranker for a travel and compliance
knowledge system.

Your job is ONLY to evaluate how relevant each candidate
document is to the user's query.

USER QUERY:
{query}

Evaluate every candidate independently.

Scoring guidance:

90-100:
The candidate directly contains the information needed
to answer the query.

70-89:
The candidate is highly relevant and provides important
supporting information.

40-69:
The candidate is related to the same topic but does not
directly answer the query.

1-39:
The candidate has only weak or incidental relevance.

0:
The candidate is unrelated.

Important rules:

1. Prefer explicit evidence over generic semantic similarity.

2. Exact entities and terms in the query are important.
   For example, if the query asks about a drone,
   a document explicitly mentioning drones is stronger
   evidence than a generic document about entering
   Singapore.

3. Do not assume facts that are not present in the
   candidate.

4. Visa documents should not be considered relevant to
   a customs-goods question unless the query actually
   concerns visas or immigration requirements.

5. Score every supplied candidate.

6. Return each chunk_id exactly as supplied.

CANDIDATES:

{candidate_text}
""".strip()

        response = (
            self.structured_llm.invoke(
                prompt
            )
        )

        # =================================================
        # Build lookup from Claude output
        # =================================================

        score_lookup: dict[
            str,
            CandidateScore,
        ] = {}

        for item in response.results:

            # Defensive clamp in case model returns
            # something outside the requested range.
            item.relevance_score = max(
                0,
                min(
                    100,
                    item.relevance_score,
                ),
            )

            score_lookup[
                item.chunk_id
            ] = item

        # =================================================
        # Join Claude scores back to HybridResult
        # =================================================

        reranked_results: list[
            RerankedResult
        ] = []

        for candidate in candidates:

            chunk_id = str(
                candidate
                .document
                .metadata
                .get(
                    "chunk_id",
                    "",
                )
            )

            assessment = (
                score_lookup.get(
                    chunk_id
                )
            )

            # If Claude accidentally omitted a candidate,
            # keep it but give it zero relevance rather
            # than crashing the whole request.
            if assessment is None:

                reranked_results.append(
                    RerankedResult(
                        hybrid_result=(
                            candidate
                        ),

                        rerank_score=0,

                        rerank_reason=(
                            "Candidate was not scored "
                            "by the reranker."
                        ),
                    )
                )

                continue

            reranked_results.append(
                RerankedResult(
                    hybrid_result=(
                        candidate
                    ),

                    rerank_score=(
                        assessment
                        .relevance_score
                    ),

                    rerank_reason=(
                        assessment
                        .reason
                    ),
                )
            )

        # =================================================
        # Final ordering
        # =================================================

        reranked_results.sort(
            key=lambda item: (
                item.rerank_score,
                item.hybrid_result.fusion_score,
            ),
            reverse=True,
        )

        return (
            reranked_results[
                :final_k
            ]
        )