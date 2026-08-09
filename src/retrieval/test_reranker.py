from __future__ import annotations

from src.retrieval.hybrid_retriever import (
    HybridRetriever,
)

from src.retrieval.reranker import (
    ClaudeReranker,
)


# =========================================================
# Formatting helper
# =========================================================

def show_optional_rank(
    value: int | None,
) -> str:

    if value is None:
        return "-"

    return str(value)


# =========================================================
# Main
# =========================================================

def main() -> None:

    query = (
        "Can I bring a drone into Singapore?"
    )

    # =====================================================
    # Step 1
    # Candidate generation
    # =====================================================

    print(
        "\n===================================="
    )

    print(
        "STEP 1: HYBRID RETRIEVAL"
    )

    print(
        "===================================="
    )

    hybrid_retriever = (
        HybridRetriever()
    )

    hybrid_results = (
        hybrid_retriever.search(
            query=query,

            vector_k=20,

            bm25_k=20,

            final_k=10,
        )
    )

    print(
        f"\nHybrid candidates: "
        f"{len(hybrid_results)}"
    )

    # =====================================================
    # Show pre-reranking order
    # =====================================================

    print(
        "\n--- BEFORE RERANKING ---"
    )

    for rank, result in enumerate(
        hybrid_results,
        start=1,
    ):

        metadata = (
            result
            .document
            .metadata
        )

        print(
            f"\n{rank}. "
            f"{metadata.get('title')}"
        )

        print(
            f"   Fusion: "
            f"{result.fusion_score:.6f}"
        )

        print(
            f"   Vector rank: "
            f"{show_optional_rank(result.vector_rank)}"
        )

        print(
            f"   BM25 rank: "
            f"{show_optional_rank(result.bm25_rank)}"
        )

    # =====================================================
    # Step 2
    # Claude reranking
    # =====================================================

    print(
        "\n\n===================================="
    )

    print(
        "STEP 2: CLAUDE RERANKING"
    )

    print(
        "===================================="
    )

    reranker = (
        ClaudeReranker()
    )

    final_results = (
        reranker.rerank(
            query=query,

            candidates=(
                hybrid_results
            ),

            final_k=5,
        )
    )

    # =====================================================
    # Final output
    # =====================================================

    print(
        "\n\n===================================="
    )

    print(
        "FINAL TOP 5"
    )

    print(
        "===================================="
    )

    print(
        f"\nQuery:\n{query}"
    )

    for rank, result in enumerate(
        final_results,
        start=1,
    ):

        hybrid = (
            result.hybrid_result
        )

        document = (
            hybrid.document
        )

        metadata = (
            document.metadata
        )

        print(
            "\n\n"
            "===================================="
        )

        print(
            f"FINAL RANK {rank}"
        )

        print(
            "===================================="
        )

        print(
            "\nRerank score:"
        )

        print(
            result.rerank_score
        )

        print(
            "\nRerank reason:"
        )

        print(
            result.rerank_reason
        )

        print(
            "\nHybrid fusion score:"
        )

        print(
            f"{hybrid.fusion_score:.6f}"
        )

        print(
            "\nVector rank:"
        )

        print(
            show_optional_rank(
                hybrid.vector_rank
            )
        )

        print(
            "\nBM25 rank:"
        )

        print(
            show_optional_rank(
                hybrid.bm25_rank
            )
        )

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
            "\n--- Content ---"
        )

        print(
            document.page_content
        )


if __name__ == "__main__":
    main()