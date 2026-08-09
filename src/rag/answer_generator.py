from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from src.models.document import CanonicalDocument


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

load_dotenv(
    PROJECT_ROOT / ".env"
)


DEFAULT_ANTHROPIC_MODEL = (
    "claude-sonnet-4-6"
)


@dataclass
class Evidence:
    """
    One full parent document supplied to the final LLM.
    """

    citation_id: str

    document: CanonicalDocument

    rerank_score: int


class AnswerGenerator:
    """
    Generate the final grounded answer from retrieved
    parent documents.

    Claude must answer only from supplied evidence.
    """

    def __init__(self) -> None:

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
            f"Answer model: "
            f"{model_name}"
        )

        self.llm = ChatAnthropic(
            model=model_name,
            temperature=0,
            max_tokens=1500,
        )

    def _format_source(
        self,
        evidence: Evidence,
    ) -> str:
        """
        Convert one parent document into grounded context.
        """

        document = evidence.document

        parts = [
            f"[{evidence.citation_id}]",
            f"Source: {document.source}",
            f"Title: {document.title}",
        ]

        if document.heading_path:

            parts.append(
                "Heading: "
                f"{document.heading_path}"
            )

        if document.url:

            parts.append(
                f"URL: {document.url}"
            )

        if document.page is not None:

            parts.append(
                f"Page: {document.page}"
            )

        parts.append(
            "Content:\n"
            f"{document.content}"
        )

        return "\n".join(parts)

    def generate(
        self,
        query: str,
        evidence_list: list[Evidence],
    ) -> str:

        if not evidence_list:

            return (
                "I could not find enough reliable "
                "information in the available sources "
                "to answer this question."
            )

        evidence_text = (
            "\n\n"
            "====================================\n\n"
            .join(
                self._format_source(evidence)
                for evidence
                in evidence_list
            )
        )

        prompt = f"""
        You are a travel and compliance assistant.

        Answer the user's question using ONLY the evidence
        provided below.

        USER QUESTION:
        {query}

        GROUNDING RULES:

        1. Use only facts explicitly supported by the supplied
        evidence.

        2. Do not use outside knowledge.

        3. Do not strengthen or broaden a rule beyond what the
        evidence says.

        For example:
        - "before import" must not become "before travel"
        - "approval is required" must not become
            "approval is guaranteed"
        - do not infer additional restrictions unless they
            are explicitly stated.

        4. Clearly distinguish:
        - what the evidence explicitly states
        - what the evidence does not establish

        5. Cite every factual conclusion using the source labels
        exactly as provided:
        [S1], [S2], or [S1][S2].

        6. If two sources provide complementary evidence,
        combine them and cite each relevant source.

        7. Do not recommend external websites, authorities,
        procedures, fees, or actions unless the supplied
        evidence supports that recommendation.

        8. If information is missing, say:
        "The available evidence does not specify ..."

        9. Keep the answer concise and practical.
        Avoid unnecessary sections, repetition, or generic
        safety disclaimers.

        EVIDENCE:

        {evidence_text}
        """.strip()

        response = self.llm.invoke(
            prompt
        )

        content = response.content

        if isinstance(
            content,
            str,
        ):
            return content

        return str(content)