from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.models.document import CanonicalDocument


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "word"
)

CURATED_DIR = (
    PROJECT_ROOT
    / "data"
    / "curated"
)

CURATED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_PATH = (
    CURATED_DIR
    / "customs_word_documents.jsonl"
)


# =========================================================
# Source-specific semantic hierarchy
#
# Why?
#
# This Word file does not consistently use Word
# Heading 1 / Heading 2 styles.
#
# Bold is useful as a signal, but it does not reliably
# tell us whether something is H1 or H2.
#
# Therefore:
#
# formatting = generic signal
# heading map = source-specific structure rule
# =========================================================

HEADING_LEVELS = {
    # -----------------------------------------------------
    # H1
    # -----------------------------------------------------

    "what counts as an offence?": 1,

    "bringing in prohibited or controlled goods": 1,

    "bringing in contraband cigarettes": 1,

    "breaching the three-quarter tank rule": 1,

    "appeals": 1,

    "reminder": 1,

    # -----------------------------------------------------
    # H2
    # -----------------------------------------------------

    "not declaring or making an incorrect declaration": 2,

    "composition amounts for checkpoints offences": 2,

    "prohibited goods": 2,

    "controlled goods": 2,

    "composition amounts for three-quarter tank offences": 2,
}


# =========================================================
# Text helpers
# =========================================================

def normalise_heading_key(
    text: str,
) -> str:

    text = (
        text
        .replace("\xa0", " ")
        .strip()
        .casefold()
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    )


def make_slug(
    text: str,
) -> str:

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        text,
    )

    return (
        text.strip("-")
        or "section"
    )


# =========================================================
# Heading detection
# =========================================================

def detect_heading_level(
    block: dict,
    current_h1: str | None,
    previous_was_heading: bool,
) -> int | None:
    """
    Return:

        1 -> H1
        2 -> H2
        None -> normal content

    First use the source-specific hierarchy map.

    Then use bold formatting only as a fallback.
    """

    if (
        block.get("type")
        != "paragraph"
    ):

        return None

    text = (
        block.get(
            "text",
            ""
        )
        .strip()
    )

    if not text:
        return None

    key = (
        normalise_heading_key(
            text
        )
    )

    # -----------------------------------------------------
    # Strongest signal:
    # known source hierarchy
    # -----------------------------------------------------

    if key in HEADING_LEVELS:

        return (
            HEADING_LEVELS[
                key
            ]
        )

    # -----------------------------------------------------
    # Generic fallback
    # -----------------------------------------------------

    formatting = block.get(
        "formatting",
        {},
    )

    mostly_bold = formatting.get(
        "mostly_bold",
        False,
    )

    if not mostly_bold:
        return None

    # Very long bold text is more likely emphasis
    # than a heading.

    if len(text) > 100:
        return None

    # Full sentence is less likely a heading.

    if text.endswith(
        "."
    ):
        return None

    # -----------------------------------------------------
    # Adjacent bold headings:
    #
    # H1
    # H2
    #
    # If we have just seen a heading and already have H1,
    # treat the next unknown short bold heading as H2.
    # -----------------------------------------------------

    if (
        previous_was_heading
        and current_h1
    ):

        return 2

    # Otherwise default unknown bold heading to H1.

    return 1


# =========================================================
# List rendering
# =========================================================

def paragraph_to_text(
    block: dict,
) -> str:
    """
    Turn extracted paragraph into retrieval-friendly text.

    Word bullet item:
        Exceed GST relief

    becomes:
        - Exceed GST relief
    """

    text = (
        block.get(
            "text",
            ""
        )
        .strip()
    )

    if not text:
        return ""

    list_info = block.get(
        "list",
        {},
    )

    if list_info.get(
        "is_list_item",
        False,
    ):

        level = (
            list_info.get(
                "level",
                0,
            )
            or 0
        )

        indent = (
            "  "
            * level
        )

        return (
            f"{indent}- {text}"
        )

    return text


# =========================================================
# Table rendering
# =========================================================

def table_to_text(
    rows: list[list[str]],
) -> str:
    """
    Convert Word table to retrieval-friendly text
    without losing header/value relationships.
    """

    if not rows:
        return ""

    headers = [
        header.strip()
        for header
        in rows[0]
    ]

    output_rows = []

    for row in rows[1:]:

        row_parts = []

        for index, cell in enumerate(
            row
        ):

            cell = (
                cell.strip()
            )

            if not cell:
                continue

            if index < len(
                headers
            ):

                header = (
                    headers[index]
                    or f"Column {index + 1}"
                )

                row_parts.append(
                    f"{header}: "
                    f"{cell}"
                )

            else:

                row_parts.append(
                    cell
                )

        if row_parts:

            output_rows.append(
                "\n".join(
                    row_parts
                )
            )

    return "\n\n".join(
        output_rows
    )


# =========================================================
# Hyperlink helpers
# =========================================================

def add_unique_links(
    existing_links: list[dict],
    new_links: list[dict],
) -> None:

    seen = {
        (
            link.get("text"),
            link.get("url"),
        )
        for link
        in existing_links
    }

    for link in new_links:

        key = (
            link.get("text"),
            link.get("url"),
        )

        if (
            key not in seen
            and link.get("url")
        ):

            existing_links.append(
                link
            )

            seen.add(
                key
            )


def render_links(
    links: list[dict],
) -> str:
    """
    Keep source URLs available to the LLM.

    Example:

    References:
    - Customs Appeals Form: https://...
    """

    if not links:
        return ""

    lines = [
        "References:"
    ]

    for link in links:

        text = (
            link.get(
                "text"
            )
            or "Source link"
        )

        url = link.get(
            "url"
        )

        if url:

            lines.append(
                f"- {text}: {url}"
            )

    if len(lines) == 1:
        return ""

    return "\n".join(
        lines
    )


# =========================================================
# Topic metadata
# =========================================================

def derive_topic(
    h1: str | None,
    h2: str | None,
) -> str:
    """
    Give related Word/PDF knowledge a shared topic.

    Later the PDF curator can also use:

        controlled_prohibited_goods

    This allows multi-source retrieval.
    """

    if (
        h1
        and normalise_heading_key(h1)
        ==
        "bringing in prohibited or controlled goods"
    ):

        return (
            "controlled_prohibited_goods"
        )

    base = (
        h1
        or h2
        or "overview"
    )

    return (
        make_slug(base)
        .replace(
            "-",
            "_",
        )
    )


# =========================================================
# Build CanonicalDocument
# =========================================================

def build_document(
    document_title: str,
    h1: str | None,
    h2: str | None,
    content_parts: list[str],
    links: list[dict],
    source_file: str,
    section_index: int,
) -> CanonicalDocument:

    # -----------------------------------------------------
    # Most specific section becomes title
    # -----------------------------------------------------

    title = (
        h2
        or h1
        or "Overview"
    )

    # -----------------------------------------------------
    # Full semantic path
    # -----------------------------------------------------

    path_parts = [
        document_title
    ]

    if h1:

        path_parts.append(
            h1
        )

    if h2:

        path_parts.append(
            h2
        )

    heading_path = (
        " > ".join(
            path_parts
        )
    )

    # -----------------------------------------------------
    # Main body
    # -----------------------------------------------------

    content = (
        "\n\n".join(
            content_parts
        )
        .strip()
    )

    # -----------------------------------------------------
    # Preserve useful URLs
    # -----------------------------------------------------

    link_text = (
        render_links(
            links
        )
    )

    if link_text:

        content = (
            f"{content}\n\n"
            f"{link_text}"
        )

    topic = derive_topic(
        h1,
        h2,
    )

    return CanonicalDocument(
        doc_id=(
            f"customs-word-"
            f"{section_index:02d}-"
            f"{make_slug(title)}"
        ),

        source=(
            "Singapore Customs"
        ),

        source_type=(
            "word"
        ),

        title=title,

        heading_path=(
            heading_path
        ),

        content=content,

        url=None,

        page=None,

        metadata={
            "source_file": (
                source_file
            ),

            "document_title": (
                document_title
            ),

            "section_index": (
                section_index
            ),

            "h1": h1,

            "h2": h2,

            "topic": topic,

            # Word mainly supplies operational rules.
            # PDF can later use content_role="examples".
            "content_role": "rules",

            "links": links,
        },
    )


# =========================================================
# Flush semantic section
# =========================================================

def flush_section(
    document_title: str,
    current_h1: str | None,
    current_h2: str | None,
    current_content: list[str],
    current_links: list[dict],
    source_file: str,
    section_index: int,
) -> CanonicalDocument | None:

    if not current_content:
        return None

    return build_document(
        document_title=(
            document_title
        ),

        h1=(
            current_h1
        ),

        h2=(
            current_h2
        ),

        content_parts=(
            current_content
        ),

        links=(
            current_links
        ),

        source_file=(
            source_file
        ),

        section_index=(
            section_index
        ),
    )


# =========================================================
# Main curation logic
# =========================================================

def curate_word_document(
    data: dict,
) -> list[CanonicalDocument]:

    blocks = data.get(
        "blocks",
        [],
    )

    if not blocks:
        return []

    # -----------------------------------------------------
    # First meaningful paragraph = document title
    # -----------------------------------------------------

    document_title = (
        blocks[0]
        .get(
            "text",
            "Travel Rules and Penalties",
        )
        .strip()
    )

    documents = []

    current_h1 = None
    current_h2 = None

    current_content = []
    current_links = []

    section_index = 1

    previous_was_heading = False

    # Skip first block:
    # it is document title.

    for block in blocks[1:]:

        block_type = (
            block.get(
                "type"
            )
        )

        # =================================================
        # Paragraph
        # =================================================

        if block_type == "paragraph":

            heading_level = (
                detect_heading_level(
                    block,
                    current_h1,
                    previous_was_heading,
                )
            )

            # ---------------------------------------------
            # New heading
            # ---------------------------------------------

            if heading_level:

                # Flush content belonging to previous
                # semantic section.

                document = flush_section(
                    document_title=(
                        document_title
                    ),

                    current_h1=(
                        current_h1
                    ),

                    current_h2=(
                        current_h2
                    ),

                    current_content=(
                        current_content
                    ),

                    current_links=(
                        current_links
                    ),

                    source_file=(
                        data["source_file"]
                    ),

                    section_index=(
                        section_index
                    ),
                )

                if document:

                    documents.append(
                        document
                    )

                    section_index += 1

                current_content = []
                current_links = []

                heading_text = (
                    block[
                        "text"
                    ]
                    .strip()
                )

                # -----------------------------------------
                # H1
                # -----------------------------------------

                if heading_level == 1:

                    current_h1 = (
                        heading_text
                    )

                    current_h2 = None

                # -----------------------------------------
                # H2
                # -----------------------------------------

                elif heading_level == 2:

                    current_h2 = (
                        heading_text
                    )

                previous_was_heading = True

                continue

            # ---------------------------------------------
            # Normal paragraph
            # ---------------------------------------------

            text = (
                paragraph_to_text(
                    block
                )
            )

            if text:

                current_content.append(
                    text
                )

            add_unique_links(
                current_links,
                block.get(
                    "hyperlinks",
                    [],
                ),
            )

            previous_was_heading = False

        # =================================================
        # Table
        # =================================================

        elif block_type == "table":

            table_text = (
                table_to_text(
                    block.get(
                        "rows",
                        [],
                    )
                )
            )

            if table_text:

                current_content.append(
                    table_text
                )

            add_unique_links(
                current_links,
                block.get(
                    "hyperlinks",
                    [],
                ),
            )

            previous_was_heading = False

    # =====================================================
    # Flush final semantic section
    # =====================================================

    final_document = (
        flush_section(
            document_title=(
                document_title
            ),

            current_h1=(
                current_h1
            ),

            current_h2=(
                current_h2
            ),

            current_content=(
                current_content
            ),

            current_links=(
                current_links
            ),

            source_file=(
                data["source_file"]
            ),

            section_index=(
                section_index
            ),
        )
    )

    if final_document:

        documents.append(
            final_document
        )

    return documents


# =========================================================
# Main
# =========================================================

def main() -> None:

    input_files = sorted(
        PROCESSED_DIR.glob(
            "*.json"
        )
    )

    if not input_files:

        raise FileNotFoundError(
            "No processed Word JSON "
            f"found in {PROCESSED_DIR}"
        )

    all_documents = []

    for input_path in input_files:

        print(
            f"\nCurating: "
            f"{input_path.name}"
        )

        with open(
            input_path,
            "r",
            encoding="utf-8",
        ) as file:

            data = (
                json.load(
                    file
                )
            )

        documents = (
            curate_word_document(
                data
            )
        )

        all_documents.extend(
            documents
        )

        print(
            "Semantic documents created: "
            f"{len(documents)}"
        )

        for document in documents:

            print(
                f"- "
                f"{document.heading_path}"
            )

    # =====================================================
    # Save JSONL
    # =====================================================

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        for document in all_documents:

            file.write(
                document
                .model_dump_json()
                + "\n"
            )

    print(
        f"\nTotal documents: "
        f"{len(all_documents)}"
    )

    print(
        f"Saved to: "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()