from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


# =========================================================
# Environment
# =========================================================

load_dotenv(
    PROJECT_ROOT / ".env"
)


# =========================================================
# Embedding configuration
# =========================================================

DEFAULT_EMBEDDING_MODEL = (
    "BAAI/bge-small-en-v1.5"
)


# =========================================================
# Create embeddings
# =========================================================

def create_embeddings() -> HuggingFaceEmbeddings:
    """
    Create the embedding model used for both:

    1. document indexing
    2. query retrieval

    The same embedding model must be used for both.
    """

    model_name = os.getenv(
        "EMBEDDING_MODEL",
        DEFAULT_EMBEDDING_MODEL,
    )

    print(
        f"Embedding model: "
        f"{model_name}"
    )

    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,

        model_kwargs={
            "device": "cpu",
        },

        encode_kwargs={
            "normalize_embeddings": True,
        },
    )

    return embeddings