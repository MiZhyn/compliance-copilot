from __future__ import annotations

import json
from pathlib import Path

from src.models.document import CanonicalDocument


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


class ParentDocumentStore:
    """
    Store original semantic parent documents.

    Vector/BM25 retrieval searches smaller child chunks.
    After reranking, parent_doc_id is used to recover
    the full CanonicalDocument.
    """

    def __init__(self) -> None:

        self.documents: dict[
            str,
            CanonicalDocument,
        ] = {}

        self._load_documents()

        print(
            f"Parent documents loaded: "
            f"{len(self.documents)}"
        )

    def _load_documents(self) -> None:

        document_files = sorted(
            CURATED_DIR.glob(
                "*_documents.jsonl"
            )
        )

        if not document_files:

            raise FileNotFoundError(
                "No *_documents.jsonl files "
                f"found in {CURATED_DIR}"
            )

        for file_path in document_files:

            with open(
                file_path,
                "r",
                encoding="utf-8",
            ) as file:

                for line_number, line in enumerate(
                    file,
                    start=1,
                ):

                    line = line.strip()

                    if not line:
                        continue

                    try:

                        raw = json.loads(line)

                        document = (
                            CanonicalDocument
                            .model_validate(raw)
                        )

                    except Exception as exc:

                        raise ValueError(
                            f"Failed loading "
                            f"{file_path.name}, "
                            f"line {line_number}: "
                            f"{exc}"
                        ) from exc

                    if (
                        document.doc_id
                        in self.documents
                    ):

                        raise ValueError(
                            "Duplicate parent doc_id: "
                            f"{document.doc_id}"
                        )

                    self.documents[
                        document.doc_id
                    ] = document

    def get(
        self,
        parent_doc_id: str,
    ) -> CanonicalDocument | None:

        return self.documents.get(
            parent_doc_id
        )

    def require(
        self,
        parent_doc_id: str,
    ) -> CanonicalDocument:

        document = self.get(
            parent_doc_id
        )

        if document is None:

            raise KeyError(
                "Parent document not found: "
                f"{parent_doc_id}"
            )

        return document