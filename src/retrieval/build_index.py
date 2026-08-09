from __future__ import annotations

import json
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)

from src.models.document import (
    CanonicalDocument,
)

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

CURATED_DIR = (
    PROJECT_ROOT
    / "data"
    / "curated"
)

VECTORSTORE_DIR = (
    PROJECT_ROOT
    / "data"
    / "vectorstore"
    / "chroma"
)


# =========================================================
# Retrieval configuration
# =========================================================

COLLECTION_NAME = (
    "travel_compliance_knowledge"
)


# ---------------------------------------------------------
# Parent / child strategy
#
# If a curated semantic document is short, keep it intact.
#
# If it is long, split it into smaller child chunks for
# retrieval.
# ---------------------------------------------------------

MAX_PARENT_CHARS = 1200

CHILD_CHUNK_SIZE = 700

CHILD_CHUNK_OVERLAP = 100


# =========================================================
# Load CanonicalDocuments
# =========================================================

def load_canonical_documents(
) -> list[CanonicalDocument]:
    """
    Load every JSONL file in data/curated.

    Each JSONL line must follow the shared
    CanonicalDocument schema.
    """

    jsonl_files = sorted(
        CURATED_DIR.glob(
            "*_documents.jsonl"
        )
    )

    if not jsonl_files:

        raise FileNotFoundError(
            "No curated JSONL files "
            f"found in {CURATED_DIR}"
        )

    documents: list[
        CanonicalDocument
    ] = []

    for file_path in jsonl_files:

        print(
            f"Loading: "
            f"{file_path.name}"
        )

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:

            for (
                line_number,
                line,
            ) in enumerate(
                file,
                start=1,
            ):

                line = line.strip()

                if not line:
                    continue

                try:

                    data = json.loads(
                        line
                    )

                    document = (
                        CanonicalDocument
                        .model_validate(
                            data
                        )
                    )

                    documents.append(
                        document
                    )

                except Exception as exc:

                    raise ValueError(
                        "Failed to parse "
                        f"{file_path.name}, "
                        f"line {line_number}: "
                        f"{exc}"
                    ) from exc

    return documents


# =========================================================
# Embedding content preparation
# =========================================================

def get_semantic_content(
    document: CanonicalDocument,
) -> str:
    """
    Return the semantic body used for chunking.

    Word documents may contain:

        References:
        - xxx: https://...

    URLs are useful for final answers but provide little
    semantic value during embedding, so remove this
    References block from the text sent for embedding.

    The links remain preserved in CanonicalDocument
    metadata.
    """

    content = (
        document.content
        .strip()
    )

    reference_marker = (
        "\n\nReferences:"
    )

    if reference_marker in content:

        content = (
            content.split(
                reference_marker,
                1,
            )[0]
            .strip()
        )

    return content


def build_embedding_text(
    document: CanonicalDocument,
    child_content: str,
) -> str:
    """
    Add semantic context back to every child chunk.

    Example:

        Travel Rules and Penalties
        > Bringing in Prohibited or Controlled Goods
        > Controlled Goods

        Controlled Goods

        These goods require approval...

    This prevents small child chunks from losing
    their business / document context.
    """

    parts: list[str] = []

    if document.heading_path:

        parts.append(
            document.heading_path
        )

    if document.title:

        title_already_in_heading = (
            document.heading_path
            and document.title.casefold()
            in document.heading_path.casefold()
        )

        if not title_already_in_heading:

            parts.append(
                document.title
            )

    if child_content.strip():

        parts.append(
            child_content.strip()
        )

    return "\n\n".join(
        parts
    )


# =========================================================
# Chroma metadata
# =========================================================

def build_metadata(
    document: CanonicalDocument,
    chunk_index: int,
    chunk_count: int,
) -> dict:
    """
    Build flat metadata for Chroma.

    Chroma metadata should stay simple:
    string / int / float / bool.

    Complex nested dictionaries such as links remain in
    the original CanonicalDocument rather than being
    pushed directly into the vector store.
    """

    metadata = {
        "parent_doc_id":
            document.doc_id,

        "source":
            document.source,

        "source_type":
            document.source_type,

        "title":
            document.title,

        "chunk_index":
            chunk_index,

        "chunk_count":
            chunk_count,

        "is_split":
            chunk_count > 1,
    }

    # -----------------------------------------------------
    # Standard canonical fields
    # -----------------------------------------------------

    if document.heading_path:

        metadata[
            "heading_path"
        ] = document.heading_path

    if document.url:

        metadata[
            "url"
        ] = document.url

    if document.page is not None:

        metadata[
            "page"
        ] = int(
            document.page
        )

    # -----------------------------------------------------
    # Useful custom metadata
    # -----------------------------------------------------

    topic = (
        document.metadata.get(
            "topic"
        )
    )

    if topic is not None:

        metadata[
            "topic"
        ] = str(
            topic
        )

    content_role = (
        document.metadata.get(
            "content_role"
        )
    )

    if content_role is not None:

        metadata[
            "content_role"
        ] = str(
            content_role
        )

    source_file = (
        document.metadata.get(
            "source_file"
        )
    )

    if source_file is not None:

        metadata[
            "source_file"
        ] = str(
            source_file
        )

    section_number = (
        document.metadata.get(
            "section_number"
        )
    )

    if section_number is not None:

        metadata[
            "section_number"
        ] = str(
            section_number
        )

    country = (
        document.metadata.get(
            "country"
        )
    )

    if country is not None:

        metadata[
            "country"
        ] = str(
            country
        )

    return metadata


# =========================================================
# Parent -> child transformation
# =========================================================

def create_index_documents(
    canonical_documents: list[
        CanonicalDocument
    ],
) -> list[Document]:
    """
    Convert semantic parent documents into the actual
    documents stored in the vector index.

    Short semantic units:
        parent -> one child

    Long semantic units:
        parent -> multiple smaller children
    """

    splitter = (
        RecursiveCharacterTextSplitter(
            chunk_size=(
                CHILD_CHUNK_SIZE
            ),

            chunk_overlap=(
                CHILD_CHUNK_OVERLAP
            ),

            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        )
    )

    index_documents: list[
        Document
    ] = []

    split_parent_count = 0

    unsplit_parent_count = 0

    for document in canonical_documents:

        semantic_content = (
            get_semantic_content(
                document
            )
        )

        if not semantic_content:

            print(
                "Skipping empty document: "
                f"{document.doc_id}"
            )

            continue

        # -------------------------------------------------
        # Short semantic document:
        # preserve complete semantic unit.
        # -------------------------------------------------

        if (
            len(
                semantic_content
            )
            <= MAX_PARENT_CHARS
        ):

            chunks = [
                semantic_content
            ]

            unsplit_parent_count += 1

        # -------------------------------------------------
        # Long semantic document:
        # use smaller children for retrieval.
        # -------------------------------------------------

        else:

            chunks = (
                splitter.split_text(
                    semantic_content
                )
            )

            split_parent_count += 1

        chunk_count = len(
            chunks
        )

        for (
            chunk_index,
            chunk,
        ) in enumerate(
            chunks
        ):

            embedding_text = (
                build_embedding_text(
                    document=document,
                    child_content=chunk,
                )
            )

            chunk_id = (
                f"{document.doc_id}"
                f"::child-"
                f"{chunk_index:03d}"
            )

            metadata = (
                build_metadata(
                    document=document,
                    chunk_index=(
                        chunk_index
                    ),
                    chunk_count=(
                        chunk_count
                    ),
                )
            )

            # ---------------------------------------------
            # Store our chunk id in metadata as well.
            #
            # We will also pass it as Chroma's actual ID
            # during add_documents().
            # ---------------------------------------------

            metadata[
                "chunk_id"
            ] = chunk_id

            index_document = Document(
                page_content=(
                    embedding_text
                ),

                metadata=(
                    metadata
                ),
            )

            index_documents.append(
                index_document
            )

    print(
        "\n=== Chunking Summary ==="
    )

    print(
        "Parent documents: "
        f"{len(canonical_documents)}"
    )

    print(
        "Parents kept intact: "
        f"{unsplit_parent_count}"
    )

    print(
        "Parents requiring split: "
        f"{split_parent_count}"
    )

    print(
        "Index children created: "
        f"{len(index_documents)}"
    )

    return index_documents


# =========================================================
# Build vector store
# =========================================================

def build_vectorstore(
    index_documents: list[
        Document
    ],
) -> Chroma:
    """
    Generate local BGE embeddings and write vectors
    into a persistent local Chroma database.
    """

    if not index_documents:

        raise ValueError(
            "No index documents were created."
        )

    embeddings = (
        create_embeddings()
    )

    # -----------------------------------------------------
    # For this demo we rebuild the index from scratch.
    #
    # This prevents duplicate vectors when the ingestion
    # script is rerun during development.
    # -----------------------------------------------------

    if VECTORSTORE_DIR.exists():

        print(
            "\nRemoving existing "
            "vector store..."
        )

        shutil.rmtree(
            VECTORSTORE_DIR
        )

    VECTORSTORE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vectorstore = Chroma(
        collection_name=(
            COLLECTION_NAME
        ),

        embedding_function=(
            embeddings
        ),

        persist_directory=str(
            VECTORSTORE_DIR
        ),
    )

    ids = [
        document.metadata[
            "chunk_id"
        ]
        for document
        in index_documents
    ]

    print(
        "\nGenerating local embeddings "
        "and writing to Chroma..."
    )

    vectorstore.add_documents(
        documents=(
            index_documents
        ),

        ids=ids,
    )

    print(
        "Vectors written: "
        f"{len(ids)}"
    )

    return vectorstore


# =========================================================
# Main
# =========================================================

def main() -> None:

    print(
        "===================================="
    )

    print(
        "Building Travel & Compliance Index"
    )

    print(
        "===================================="
    )

    # =====================================================
    # Step 1
    # Load curated semantic documents
    # =====================================================

    print(
        "\n=== 1. Loading canonical documents ==="
    )

    canonical_documents = (
        load_canonical_documents()
    )

    print(
        "\nCanonical documents loaded: "
        f"{len(canonical_documents)}"
    )

    # =====================================================
    # Step 2
    # Create retrieval children
    # =====================================================

    print(
        "\n=== 2. Creating index children ==="
    )

    index_documents = (
        create_index_documents(
            canonical_documents
        )
    )

    # =====================================================
    # Step 3
    # Embedding + Chroma
    # =====================================================

    print(
        "\n=== 3. Building vector store ==="
    )

    build_vectorstore(
        index_documents
    )

    print(
        "\n===================================="
    )

    print(
        "Index build complete"
    )

    print(
        "===================================="
    )

    print(
        f"\nChroma directory:\n"
        f"{VECTORSTORE_DIR}"
    )


if __name__ == "__main__":
    main()