from __future__ import annotations

from src.rag.pipeline import (
    RAGPipeline,
)


def main() -> None:

    query = (
        "Can I bring a drone into Singapore?"
    )

    print(
        "\n===================================="
    )

    print(
        "END-TO-END RAG TEST"
    )

    print(
        "===================================="
    )

    print(
        f"\nQuestion:\n{query}"
    )

    pipeline = (
        RAGPipeline()
    )

    result = (
        pipeline.ask(
            query
        )
    )

    # =====================================================
    # Final answer
    # =====================================================

    print(
        "\n\n===================================="
    )

    print(
        "FINAL ANSWER"
    )

    print(
        "===================================="
    )

    print(
        f"\n{result.answer}"
    )

    # =====================================================
    # Evidence
    # =====================================================

    print(
        "\n\n===================================="
    )

    print(
        "EVIDENCE USED"
    )

    print(
        "===================================="
    )

    for evidence in result.evidence:

        document = (
            evidence.document
        )

        print(
            f"\n[{evidence.citation_id}]"
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

        if document.url:

            print(
                f"URL: "
                f"{document.url}"
            )

        if document.page is not None:

            print(
                f"Page: "
                f"{document.page}"
            )

        print(
            "\nFull parent content:"
        )

        print(
            document.content
        )


if __name__ == "__main__":
    main()