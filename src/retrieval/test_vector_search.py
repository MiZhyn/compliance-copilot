from __future__ import annotations

from pathlib import Path

from langchain_chroma import Chroma

from src.retrieval.embeddings import (
    create_embeddings,
)


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

VECTORSTORE_DIR = (
    PROJECT_ROOT
    / "data"
    / "vectorstore"
    / "chroma"
)


# =========================================================
# Configuration
# =========================================================

COLLECTION_NAME = (
    "travel_compliance_knowledge"
)


# =========================================================
# Load existing Chroma vector store
# =========================================================

def load_vectorstore() -> Chroma:
    """
    Load the Chroma vector store that was already built
    by build_index.py.

    This script does NOT rebuild the index.
    """

    if not VECTORSTORE_DIR.exists():

        raise FileNotFoundError(
            "Vector store does not exist.\n"
            "Please run first:\n"
            "python -m src.retrieval.build_index"
        )

    # IMPORTANT:
    # Use the same embedding model used during indexing.
    embeddings = create_embeddings()

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(
            VECTORSTORE_DIR
        ),
    )

    return vectorstore


# =========================================================
# Vector search
# =========================================================

def search(
    query: str,
    k: int = 20,
) -> None:
    """
    Search the existing vector index and print the
    top-k retrieved child chunks.
    """

    vectorstore = load_vectorstore()

    retrieval_query = (
    "Represent this sentence for "
    "searching relevant passages: "
    + query
    )

    results = (
        vectorstore
        .similarity_search_with_score(
            query=retrieval_query,
            k=k,
        )
    )

    print(
        "\n===================================="
    )

    print("VECTOR SEARCH")

    print(
        "===================================="
    )

    print(
        f"\nQuery:\n{query}"
    )

    print(
        f"\nTop K: {k}"
    )

    if not results:

        print(
            "\nNo results found."
        )

        return

    for rank, (
        document,
        score,
    ) in enumerate(
        results,
        start=1,
    ):

        metadata = (
            document.metadata
        )

        print(
            "\n\n"
            "===================================="
        )

        print(
            f"RANK {rank}"
        )

        print(
            "===================================="
        )

        print(
            f"Distance score: "
            f"{score:.4f}"
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
            "\nSource type:"
        )

        print(
            metadata.get(
                "source_type",
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
            "\nHeading path:"
        )

        print(
            metadata.get(
                "heading_path",
                "N/A",
            )
        )

        print(
            "\nParent document:"
        )

        print(
            metadata.get(
                "parent_doc_id",
                "N/A",
            )
        )

        print(
            "\nChunk ID:"
        )

        print(
            metadata.get(
                "chunk_id",
                "N/A",
            )
        )

        print(
            "\nChunk position:"
        )

        print(
            f"{metadata.get('chunk_index', 'N/A')} "
            f"/ "
            f"{metadata.get('chunk_count', 'N/A')}"
        )

        print(
            "\nTopic:"
        )

        print(
            metadata.get(
                "topic",
                "N/A",
            )
        )

        print(
            "\nContent role:"
        )

        print(
            metadata.get(
                "content_role",
                "N/A",
            )
        )

        print(
            "\n--- Retrieved Content ---"
        )

        print(
            document.page_content
        )


# =========================================================
# Main
# =========================================================

def main() -> None:

    query = (
        "Can I bring a drone into Singapore?"
    )

    search(
        query=query,
        k=20,
    )


if __name__ == "__main__":
    main()