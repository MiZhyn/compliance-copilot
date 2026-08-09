from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from langchain_chroma import Chroma
from langchain_core.documents import Document

from nltk.stem import PorterStemmer
from rank_bm25 import BM25Okapi

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

DEFAULT_VECTOR_K = 20

DEFAULT_BM25_K = 20

DEFAULT_FINAL_K = 10

# Standard baseline for Reciprocal Rank Fusion.
# This is not a relevance threshold.
RRF_K = 60


# =========================================================
# BM25 text preprocessing
# =========================================================

STEMMER = PorterStemmer()


# Very small stop-word set.
#
# We remove generic question words while keeping
# business terms such as:
#
# bring
# singapore
# visa
# goods
# permit
# drone
#
STOP_WORDS = {
    "a",
    "an",
    "the",
    "i",
    "me",
    "my",
    "you",
    "your",
    "we",
    "our",
    "can",
    "could",
    "would",
    "should",
    "do",
    "does",
    "did",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "to",
    "into",
    "in",
    "on",
    "at",
    "of",
    "for",
    "from",
    "with",
    "and",
    "or",
    "if",
    "this",
    "that",
    "it",
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
}


def tokenize_for_bm25(
    text: str,
) -> list[str]:
    """
    Convert text into lexical tokens for BM25.

    Example:

        "Can I bring drones into Singapore?"

    becomes roughly:

        [
            "bring",
            "drone",
            "singapor"
        ]

    Porter stemming helps lexical retrieval match
    simple variants such as:

        drone / drones
        controlled / controlling
        penalties / penalty
    """

    raw_tokens = re.findall(
        r"[A-Za-z0-9]+",
        text.lower(),
    )

    processed_tokens: list[str] = []

    for token in raw_tokens:

        if token in STOP_WORDS:
            continue

        stemmed_token = (
            STEMMER.stem(token)
        )

        processed_tokens.append(
            stemmed_token
        )

    return processed_tokens


# =========================================================
# Hybrid result object
# =========================================================

@dataclass
class HybridResult:
    """
    One candidate after combining Vector and BM25 results.
    """

    document: Document

    fusion_score: float = 0.0

    vector_rank: int | None = None

    vector_distance: float | None = None

    bm25_rank: int | None = None

    bm25_score: float | None = None


# =========================================================
# Hybrid Retriever
# =========================================================

class HybridRetriever:
    """
    Hybrid retrieval pipeline:

        Query
          ↓
        ┌─────────────┐
        │             │
        ↓             ↓
      Vector         BM25
        ↓             ↓
        └──────┬──────┘
               ↓
              RRF
               ↓
          Final ranking
    """

    def __init__(
        self,
    ) -> None:

        # =================================================
        # 1. Load embedding model
        # =================================================

        self.embeddings = (
            create_embeddings()
        )

        # =================================================
        # 2. Open existing Chroma
        # =================================================

        if not VECTORSTORE_DIR.exists():

            raise FileNotFoundError(
                "Vector store does not exist.\n"
                "Run first:\n"
                "python -m src.retrieval.build_index"
            )

        self.vectorstore = Chroma(
            collection_name=(
                COLLECTION_NAME
            ),

            embedding_function=(
                self.embeddings
            ),

            persist_directory=str(
                VECTORSTORE_DIR
            ),
        )

        # =================================================
        # 3. Read exact same child corpus from Chroma
        # =================================================

        self.documents = (
            self._load_index_documents()
        )

        print(
            f"Hybrid corpus documents: "
            f"{len(self.documents)}"
        )

        # =================================================
        # 4. Build BM25 index
        # =================================================

        tokenized_corpus = [
            tokenize_for_bm25(
                document.page_content
            )
            for document
            in self.documents
        ]

        self.bm25 = BM25Okapi(
            tokenized_corpus
        )

        print(
            "BM25 index ready."
        )


    # =====================================================
    # Load existing indexed children
    # =====================================================

    def _load_index_documents(
        self,
    ) -> list[Document]:
        """
        Read documents already stored in Chroma.

        This ensures BM25 searches exactly the same
        child chunks as Vector Search.
        """

        raw_data = (
            self.vectorstore.get(
                include=[
                    "documents",
                    "metadatas",
                ]
            )
        )

        ids = (
            raw_data.get(
                "ids"
            )
            or []
        )

        texts = (
            raw_data.get(
                "documents"
            )
            or []
        )

        metadatas = (
            raw_data.get(
                "metadatas"
            )
            or []
        )

        documents: list[
            Document
        ] = []

        for (
            chunk_id,
            text,
            metadata,
        ) in zip(
            ids,
            texts,
            metadatas,
        ):

            if not text:
                continue

            metadata = (
                metadata
                or {}
            )

            # Ensure chunk_id is always available
            # for fusion.
            metadata[
                "chunk_id"
            ] = str(
                chunk_id
            )

            document = Document(
                page_content=text,
                metadata=metadata,
            )

            documents.append(
                document
            )

        if not documents:

            raise ValueError(
                "No documents found "
                "inside Chroma."
            )

        return documents


    # =====================================================
    # Vector retrieval
    # =====================================================

    def vector_search(
        self,
        query: str,
        k: int,
    ) -> list[
        tuple[
            Document,
            float,
        ]
    ]:
        """
        Dense semantic retrieval using BGE + Chroma.
        """

        embedding_query = (
            "Represent this sentence for "
            "searching relevant passages: "
            + query
        )

        results = (
            self.vectorstore
            .similarity_search_with_score(
                query=embedding_query,
                k=k,
            )
        )

        return results


    # =====================================================
    # BM25 retrieval
    # =====================================================

    def bm25_search(
        self,
        query: str,
        k: int,
    ) -> list[
        tuple[
            Document,
            float,
        ]
    ]:
        """
        Lexical retrieval using BM25.

        BM25 is useful for:

        - exact entities
        - document names
        - policy terminology
        - codes
        - numbers
        - product / item names
        """

        query_tokens = (
            tokenize_for_bm25(
                query
            )
        )

        if not query_tokens:

            return []

        scores = (
            self.bm25.get_scores(
                query_tokens
            )
        )

        ranked_indices = (
            np.argsort(
                scores
            )[::-1]
        )

        results: list[
            tuple[
                Document,
                float,
            ]
        ] = []

        for index in ranked_indices:

            score = float(
                scores[index]
            )

            # No lexical match.
            if score <= 0:
                continue

            document = (
                self.documents[
                    int(index)
                ]
            )

            results.append(
                (
                    document,
                    score,
                )
            )

            if len(results) >= k:
                break

        return results


    # =====================================================
    # RRF Fusion
    # =====================================================

    def search(
        self,
        query: str,
        vector_k: int = DEFAULT_VECTOR_K,
        bm25_k: int = DEFAULT_BM25_K,
        final_k: int = DEFAULT_FINAL_K,
        rrf_k: int = RRF_K,
    ) -> list[HybridResult]:
        """
        Run Vector + BM25 and combine their rankings
        using Reciprocal Rank Fusion.

        RRF:

            score(d)
            =
            Σ 1 / (k + rank(d))

        IMPORTANT:

        We do NOT directly combine:

            vector distance
            +
            BM25 score

        because the two raw scores use completely
        different scales.
        """

        # =================================================
        # Vector candidates
        # =================================================

        vector_results = (
            self.vector_search(
                query=query,
                k=vector_k,
            )
        )

        # =================================================
        # BM25 candidates
        # =================================================

        bm25_results = (
            self.bm25_search(
                query=query,
                k=bm25_k,
            )
        )

        # =================================================
        # Merge by chunk ID
        # =================================================

        candidates: dict[
            str,
            HybridResult,
        ] = {}

        # -------------------------------------------------
        # Vector contribution
        # -------------------------------------------------

        for rank, (
            document,
            distance,
        ) in enumerate(
            vector_results,
            start=1,
        ):

            chunk_id = str(
                document.metadata.get(
                    "chunk_id"
                )
            )

            candidate = (
                candidates.get(
                    chunk_id
                )
            )

            if candidate is None:

                candidate = (
                    HybridResult(
                        document=document
                    )
                )

                candidates[
                    chunk_id
                ] = candidate

            candidate.vector_rank = (
                rank
            )

            candidate.vector_distance = (
                float(distance)
            )

            candidate.fusion_score += (
                1.0
                /
                (
                    rrf_k
                    +
                    rank
                )
            )

        # -------------------------------------------------
        # BM25 contribution
        # -------------------------------------------------

        for rank, (
            document,
            bm25_score,
        ) in enumerate(
            bm25_results,
            start=1,
        ):

            chunk_id = str(
                document.metadata.get(
                    "chunk_id"
                )
            )

            candidate = (
                candidates.get(
                    chunk_id
                )
            )

            if candidate is None:

                candidate = (
                    HybridResult(
                        document=document
                    )
                )

                candidates[
                    chunk_id
                ] = candidate

            candidate.bm25_rank = (
                rank
            )

            candidate.bm25_score = (
                float(
                    bm25_score
                )
            )

            candidate.fusion_score += (
                1.0
                /
                (
                    rrf_k
                    +
                    rank
                )
            )

        # =================================================
        # Final ranking by fusion score
        # =================================================

        ranked_candidates = sorted(
            candidates.values(),
            key=lambda item:
                item.fusion_score,
            reverse=True,
        )

        # =================================================
        # Parent-level deduplication
        #
        # If two child chunks from the same semantic parent
        # both rank highly, keep the best one for now.
        #
        # Actual parent expansion comes later.
        # =================================================

        final_results: list[
            HybridResult
        ] = []

        seen_parents: set[
            str
        ] = set()

        for candidate in ranked_candidates:

            metadata = (
                candidate
                .document
                .metadata
            )

            parent_id = str(
                metadata.get(
                    "parent_doc_id"
                )
                or metadata.get(
                    "chunk_id"
                )
            )

            if parent_id in seen_parents:
                continue

            seen_parents.add(
                parent_id
            )

            final_results.append(
                candidate
            )

            if (
                len(final_results)
                >= final_k
            ):

                break

        return final_results