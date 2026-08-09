from __future__ import annotations

from src.retrieval.hybrid_retriever import (
    HybridRetriever,
)


# =========================================================
# Display helpers
# =========================================================

def format_optional_rank(
    value: int | None,
) -> str:

    if value is None:
        return "-"

    return str(value)


def format_optional_score(
    value: float | None,
    decimals: int = 4,
) -> str:

    if value is None:
        return "-"

    return (
        f"{value:.{decimals}f}"
    )


# =========================================================
# Main
# =========================================================

def main() -> None:

    query = (
        "Can I bring a drone into Singapore?"
    )

    print(
        "\n===================================="
    )

    print(
        "INITIALISING HYBRID RETRIEVER"
    )

    print(
        "===================================="
    )

    retriever = (
        HybridRetriever()
    )

    print(
        "\n===================================="
    )

    print(
        "HYBRID SEARCH"
    )

    print(
        "===================================="
    )

    print(
        f"\nQuery:\n{query}"
    )

    results = (
        retriever.search(
            query=query,

            vector_k=20,

            bm25_k=20,

            final_k=10,
        )
    )

    for rank, result in enumerate(
        results,
        start=1,
    ):

        document = (
            result.document
        )

        metadata = (
            document.metadata
        )

        print(
            "\n\n"
            "===================================="
        )

        print(
            f"HYBRID RANK {rank}"
        )

        print(
            "===================================="
        )

        # =============================================
        # Fusion
        # =============================================

        print(
            "\nFusion score:"
        )

        print(
            f"{result.fusion_score:.6f}"
        )

        # =============================================
        # Vector
        # =============================================

        print(
            "\nVector rank:"
        )

        print(
            format_optional_rank(
                result.vector_rank
            )
        )

        print(
            "\nVector distance:"
        )

        print(
            format_optional_score(
                result.vector_distance
            )
        )

        # =============================================
        # BM25
        # =============================================

        print(
            "\nBM25 rank:"
        )

        print(
            format_optional_rank(
                result.bm25_rank
            )
        )

        print(
            "\nBM25 score:"
        )

        print(
            format_optional_score(
                result.bm25_score
            )
        )

        # =============================================
        # Document metadata
        # =============================================

        print(
            "\nSource:"
        )

        print(
            metadata.get(
                "source",
                "N/A",
            )
        )

        print(
            "\nTitle:"
        )

        print(
            metadata.get(
                "title",
                "N/A",
            )
        )

        print(
            "\nHeading:"
        )

        print(
            metadata.get(
                "heading_path",
                "N/A",
            )
        )

        print(
            "\nParent:"
        )

        print(
            metadata.get(
                "parent_doc_id",
                "N/A",
            )
        )

        print(
            "\nChunk:"
        )

        print(
            metadata.get(
                "chunk_id",
                "N/A",
            )
        )

        # =============================================
        # Content
        # =============================================

        print(
            "\n--- Retrieved Content ---"
        )

        print(
            document.page_content
        )


if __name__ == "__main__":
    main()