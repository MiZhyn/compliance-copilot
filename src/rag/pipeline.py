from __future__ import annotations

from dataclasses import dataclass

from src.rag.answer_generator import (
    AnswerGenerator,
    Evidence,
)

from src.retrieval.hybrid_retriever import (
    HybridRetriever,
)

from src.retrieval.parent_store import (
    ParentDocumentStore,
)

from src.retrieval.reranker import (
    ClaudeReranker,
    RerankedResult,
)


# =========================================================
# Configuration
# =========================================================

VECTOR_K = 20

BM25_K = 20

HYBRID_K = 10

MAX_EVIDENCE = 5

# Demo baseline only.
# Later this should be tuned through evaluation.
MIN_RERANK_SCORE = 60


# =========================================================
# Pipeline output
# =========================================================

@dataclass
class RAGResponse:
    """
    Final output from the RAG pipeline.
    """

    answer: str

    evidence: list[Evidence]

    reranked_results: list[
        RerankedResult
    ]


# =========================================================
# RAG Pipeline
# =========================================================

class RAGPipeline:
    """
    End-to-end RAG pipeline.

    Query
        ↓
    Vector + BM25
        ↓
    RRF fusion
        ↓
    Claude reranking
        ↓
    Parent expansion
        ↓
    Grounded Claude answer
    """

    def __init__(self) -> None:

        print(
            "\nInitialising RAG pipeline..."
        )

        # -------------------------------------------------
        # Hybrid candidate retrieval
        # -------------------------------------------------

        self.hybrid_retriever = (
            HybridRetriever()
        )

        # -------------------------------------------------
        # Claude reranker
        # -------------------------------------------------

        self.reranker = (
            ClaudeReranker()
        )

        # -------------------------------------------------
        # Original semantic parent documents
        # -------------------------------------------------

        self.parent_store = (
            ParentDocumentStore()
        )

        # -------------------------------------------------
        # Final answer generation
        # -------------------------------------------------

        self.answer_generator = (
            AnswerGenerator()
        )


    # =====================================================
    # Parent expansion
    # =====================================================

    def _expand_parents(
        self,
        reranked_results: list[
            RerankedResult
        ],
    ) -> list[Evidence]:
        """
        Convert relevant retrieved child chunks back into
        their full semantic parent documents.

        Only candidates above MIN_RERANK_SCORE are used
        as final evidence.
        """

        evidence_list: list[
            Evidence
        ] = []

        seen_parent_ids: set[
            str
        ] = set()

        for result in reranked_results:

            # ---------------------------------------------
            # Filter weak evidence
            # ---------------------------------------------

            if (
                result.rerank_score
                < MIN_RERANK_SCORE
            ):
                continue

            child_document = (
                result
                .hybrid_result
                .document
            )

            parent_doc_id = (
                child_document
                .metadata
                .get(
                    "parent_doc_id"
                )
            )

            if not parent_doc_id:
                continue

            parent_doc_id = str(
                parent_doc_id
            )

            # ---------------------------------------------
            # Avoid duplicate semantic parents
            # ---------------------------------------------

            if (
                parent_doc_id
                in seen_parent_ids
            ):
                continue

            # ---------------------------------------------
            # Retrieve complete parent
            # ---------------------------------------------

            parent_document = (
                self.parent_store
                .require(
                    parent_doc_id
                )
            )

            seen_parent_ids.add(
                parent_doc_id
            )

            # ---------------------------------------------
            # Generate citation ID
            # ---------------------------------------------

            citation_id = (
                f"S{len(evidence_list) + 1}"
            )

            evidence = Evidence(
                citation_id=citation_id,

                document=(
                    parent_document
                ),

                rerank_score=(
                    result.rerank_score
                ),
            )

            evidence_list.append(
                evidence
            )

            if (
                len(evidence_list)
                >= MAX_EVIDENCE
            ):
                break

        return evidence_list


    # =====================================================
    # Ask
    # =====================================================

    def ask(
        self,
        query: str,
    ) -> RAGResponse:
        """
        Run the complete RAG flow for one user query.
        """

        # =================================================
        # Step 1
        # Hybrid retrieval
        # =================================================

        print(
            "\n[1/4] Hybrid retrieval..."
        )

        hybrid_results = (
            self.hybrid_retriever
            .search(
                query=query,

                vector_k=VECTOR_K,

                bm25_k=BM25_K,

                final_k=HYBRID_K,
            )
        )

        print(
            f"Hybrid candidates: "
            f"{len(hybrid_results)}"
        )

        # =================================================
        # Step 2
        # Claude reranking
        # =================================================

        print(
            "\n[2/4] Reranking candidates..."
        )

        reranked_results = (
            self.reranker
            .rerank(
                query=query,

                candidates=(
                    hybrid_results
                ),

                # IMPORTANT:
                # keep all 10 after reranking first.
                # thresholding happens afterwards.
                final_k=HYBRID_K,
            )
        )

        # =================================================
        # Step 3
        # Parent expansion
        # =================================================

        print(
            "\n[3/4] Expanding parent documents..."
        )

        evidence_list = (
            self._expand_parents(
                reranked_results
            )
        )

        print(
            f"Evidence documents: "
            f"{len(evidence_list)}"
        )

        # =================================================
        # Step 4
        # Final grounded answer
        # =================================================

        print(
            "\n[4/4] Generating grounded answer..."
        )

        answer = (
            self.answer_generator
            .generate(
                query=query,

                evidence_list=(
                    evidence_list
                ),
            )
        )

        return RAGResponse(
            answer=answer,

            evidence=(
                evidence_list
            ),

            reranked_results=(
                reranked_results
            ),
        )

    def retrieve_evidence(
        self,
        query: str,
    ) -> tuple[
        list[Evidence],
        list[RerankedResult],
    ]:
        """
        Retrieve grounded policy evidence without
        generating a standalone RAG answer.

        Used by orchestration layers that need evidence
        from RAG but will perform final synthesis later.
        """

        # -------------------------------------------------
        # Step 1: Hybrid retrieval
        # -------------------------------------------------

        hybrid_results = (
            self.hybrid_retriever.search(
                query=query,
                vector_k=VECTOR_K,
                bm25_k=BM25_K,
                final_k=HYBRID_K,
            )
        )

        # -------------------------------------------------
        # Step 2: Reranking
        # -------------------------------------------------

        reranked_results = (
            self.reranker.rerank(
                query=query,
                candidates=hybrid_results,
                final_k=HYBRID_K,
            )
        )

        # -------------------------------------------------
        # Step 3: Parent expansion
        # -------------------------------------------------

        evidence_list = (
            self._expand_parents(
                reranked_results
            )
        )

        return (
            evidence_list,
            reranked_results,
        )