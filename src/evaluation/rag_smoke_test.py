from __future__ import annotations

from dataclasses import dataclass

from src.rag.pipeline import (
    RAGPipeline,
)


# =========================================================
# Evaluation case
# =========================================================

@dataclass
class EvaluationCase:

    case_id: str

    query: str

    purpose: str


# =========================================================
# Small smoke-test set
# =========================================================

TEST_CASES = [

    EvaluationCase(
        case_id="customs_numeric",
        query=(
            "How much is the composition amount "
            "for undeclared cigarettes?"
        ),
        purpose=(
            "Test exact terminology and numerical "
            "retrieval from Customs documents."
        ),
    ),

    EvaluationCase(
        case_id="india_visa",
        query=(
            "Do Indian passport holders need "
            "a visa to enter Singapore?"
        ),
        purpose=(
            "Test country-specific ICA retrieval."
        ),
    ),

    EvaluationCase(
        case_id="india_vftf",
        query=(
            "Can an Indian national use the "
            "Visa Free Transit Facility?"
        ),
        purpose=(
            "Test distinction between normal visa "
            "requirements and VFTF eligibility."
        ),
    ),

    EvaluationCase(
        case_id="fst_requirements",
        query=(
            "What are the requirements for joining "
            "the Free Singapore Tour?"
        ),
        purpose=(
            "Test retrieval across FST policy "
            "and registration information."
        ),
    ),
]


# =========================================================
# Display helpers
# =========================================================

def print_separator() -> None:

    print(
        "\n"
        + "=" * 70
    )


def print_evidence(
    result,
) -> None:

    print(
        "\nEVIDENCE USED"
    )

    if not result.evidence:

        print(
            "No evidence passed "
            "the rerank threshold."
        )

        return

    for evidence in result.evidence:

        document = (
            evidence.document
        )

        print(
            "\n"
            + "-" * 60
        )

        print(
            f"[{evidence.citation_id}]"
        )

        print(
            f"Rerank score: "
            f"{evidence.rerank_score}"
        )

        print(
            f"Source: "
            f"{document.source}"
        )

        print(
            f"Title: "
            f"{document.title}"
        )

        if document.heading_path:

            print(
                f"Heading: "
                f"{document.heading_path}"
            )

        print(
            f"Parent ID: "
            f"{document.doc_id}"
        )

        print(
            "\nContent:"
        )

        print(
            document.content
        )


def print_rerank_diagnostics(
    result,
) -> None:
    """
    Show all reranked candidates.

    This helps diagnose whether failure came from:

    retrieval
        vs
    reranking
        vs
    generation.
    """

    print(
        "\nRERANK DIAGNOSTICS"
    )

    for rank, item in enumerate(
        result.reranked_results,
        start=1,
    ):

        hybrid = (
            item.hybrid_result
        )

        metadata = (
            hybrid.document.metadata
        )

        print(
            f"\n{rank}. "
            f"{metadata.get('title', 'N/A')}"
        )

        print(
            f"   Rerank score: "
            f"{item.rerank_score}"
        )

        print(
            f"   Vector rank: "
            f"{hybrid.vector_rank}"
        )

        print(
            f"   BM25 rank: "
            f"{hybrid.bm25_rank}"
        )

        print(
            f"   Fusion score: "
            f"{hybrid.fusion_score:.6f}"
        )


# =========================================================
# Main
# =========================================================

def main() -> None:

    print_separator()

    print(
        "RAG SMOKE TEST"
    )

    print_separator()

    # -----------------------------------------------------
    # Initialise once.
    #
    # Do NOT initialise the embedding model / Chroma /
    # Claude classes again for every query.
    # -----------------------------------------------------

    pipeline = (
        RAGPipeline()
    )

    for index, case in enumerate(
        TEST_CASES,
        start=1,
    ):

        print_separator()

        print(
            f"CASE {index}: "
            f"{case.case_id}"
        )

        print(
            f"\nPurpose:\n"
            f"{case.purpose}"
        )

        print(
            f"\nQuery:\n"
            f"{case.query}"
        )

        try:

            result = (
                pipeline.ask(
                    case.query
                )
            )

        except Exception as exc:

            print(
                "\nTEST FAILED WITH ERROR:"
            )

            print(
                str(exc)
            )

            continue

        # =================================================
        # Final answer
        # =================================================

        print(
            "\n\nFINAL ANSWER"
        )

        print(
            "-" * 60
        )

        print(
            result.answer
        )

        # =================================================
        # Evidence
        # =================================================

        print_evidence(
            result
        )

        # =================================================
        # Diagnostics
        # =================================================

        print_rerank_diagnostics(
            result
        )

    print_separator()

    print(
        "SMOKE TEST COMPLETE"
    )

    print_separator()


if __name__ == "__main__":
    main()