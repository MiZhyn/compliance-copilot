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
    / "visa"
)

CURATED_DIR = (
    PROJECT_ROOT
    / "data"
    / "curated"
)

OUTPUT_PATH = (
    CURATED_DIR
    / "visa_documents.jsonl"
)

CURATED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Text utilities
# =========================================================

def normalize_text(
    value: str | None,
) -> str:
    """
    Normalize extracted text while preserving
    useful paragraph and list structure.
    """

    if not value:
        return ""

    value = str(value)

    value = value.replace(
        "\xa0",
        " ",
    )

    value = re.sub(
        r"[\u200b\u200c\u200d\ufeff]",
        "",
        value,
    )

    # Horizontal whitespace
    value = re.sub(
        r"[ \t]+",
        " ",
        value,
    )

    # Clean spaces around punctuation
    value = re.sub(
        r"\s+,",
        ",",
        value,
    )

    value = re.sub(
        r"\s+\.",
        ".",
        value,
    )

    # Clean newline spacing
    value = re.sub(
        r" *\n *",
        "\n",
        value,
    )

    # Maximum two newlines
    value = re.sub(
        r"\n{3,}",
        "\n\n",
        value,
    )

    return value.strip()


def slugify(
    value: str,
) -> str:
    """
    Create stable document IDs.
    """

    value = normalize_text(
        value
    ).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    return value.strip(
        "_"
    )


def build_heading_path(
    *parts: str,
) -> str:
    """
    Build:

        ICA > India Visa Requirements > Documents Required
    """

    cleaned = [
        normalize_text(part)
        for part in parts
        if normalize_text(part)
    ]

    return " > ".join(
        cleaned
    )


# =========================================================
# CanonicalDocument helper
# =========================================================

def create_document(
    *,
    doc_id: str,
    title: str,
    heading_path: str,
    content: str,
    url: str,
    metadata: dict[str, Any],
) -> CanonicalDocument | None:
    """
    Create a canonical document only when content exists.
    """

    content = normalize_text(
        content
    )

    if not content:
        return None

    return CanonicalDocument(
        doc_id=doc_id,

        source="ica",

        source_type="web",

        title=normalize_text(
            title
        ),

        heading_path=normalize_text(
            heading_path
        ),

        content=content,

        url=normalize_text(
            url
        ) or None,

        metadata=metadata,
    )


# =========================================================
# Visa Index
# =========================================================

def curate_visa_index(
    page: dict[str, Any],
) -> list[CanonicalDocument]:
    """
    Curate:

        Check if You Need an Entry Visa
        ├── Overview
        ├── Visa Requirements
        └── Travel Documents by Countries and Places
    """

    documents = []

    page_id = page.get(
        "id",
        "ica_visa_requirements",
    )

    page_title = normalize_text(
        page.get(
            "title"
        )
    )

    url = normalize_text(
        page.get(
            "url"
        )
    )

    # =====================================================
    # 1. General overview
    # =====================================================

    overview = normalize_text(
        page.get(
            "overview"
        )
    )

    if overview:

        document = create_document(
            doc_id=(
                f"{page_id}_overview"
            ),

            title=(
                "Singapore Entry Visa Overview"
            ),

            heading_path=(
                build_heading_path(
                    "ICA",
                    page_title,
                    "Overview",
                )
            ),

            content=overview,

            url=url,

            metadata={
                "content_type": (
                    "visa_overview"
                ),

                "page_type": (
                    "visa_index"
                ),
            },
        )

        if document:
            documents.append(
                document
            )

    # =====================================================
    # 2. Index sections
    #
    # Example:
    # Visa Requirements
    # =====================================================

    for index, section in enumerate(
        page.get(
            "sections",
            [],
        ),
        start=1,
    ):

        section_title = normalize_text(
            section.get(
                "title"
            )
        )

        content = normalize_text(
            section.get(
                "content"
            )
        )

        if not content:
            continue

        document = create_document(
            doc_id=(
                f"{page_id}_"
                f"{slugify(section_title)}_"
                f"{index:02d}"
            ),

            title=section_title,

            heading_path=(
                build_heading_path(
                    "ICA",
                    page_title,
                    section_title,
                )
            ),

            content=content,

            url=url,

            metadata={
                "content_type": (
                    "visa_policy_section"
                ),

                "page_type": (
                    "visa_index"
                ),

                "section": (
                    section_title
                ),
            },
        )

        if document:
            documents.append(
                document
            )

    # =====================================================
    # 3. Country / place list
    # =====================================================

    country_list = page.get(
        "country_list",
        {},
    )

    country_list_title = normalize_text(
        country_list.get(
            "title"
        )
    )

    description = normalize_text(
        country_list.get(
            "description"
        )
    )

    countries = (
        country_list.get(
            "countries",
            []
        )
        or []
    )

    country_names = []

    for country in countries:

        name = normalize_text(
            country.get(
                "name"
            )
        )

        if name:
            country_names.append(
                name
            )

    country_parts = []

    if description:

        country_parts.append(
            description
        )

    if country_names:

        country_parts.append(
            (
                "Countries and places listed "
                "by ICA as requiring an entry visa:\n"
                + "\n".join(
                    f"- {name}"
                    for name
                    in country_names
                )
            )
        )

    country_content = (
        "\n\n".join(
            country_parts
        )
    )

    if country_content:

        document = create_document(
            doc_id=(
                f"{page_id}_"
                "travel_documents_"
                "countries_places"
            ),

            title=(
                country_list_title
                or (
                    "Travel Documents by "
                    "Countries and Places"
                )
            ),

            heading_path=(
                build_heading_path(
                    "ICA",
                    page_title,
                    (
                        country_list_title
                        or (
                            "Travel Documents "
                            "by Countries and Places"
                        )
                    ),
                )
            ),

            content=country_content,

            url=url,

            metadata={
                "content_type": (
                    "visa_country_list"
                ),

                "page_type": (
                    "visa_index"
                ),

                "country_count": (
                    len(
                        country_names
                    )
                ),
            },
        )

        if document:
            documents.append(
                document
            )

    return documents


# =========================================================
# Country-specific Visa Detail
# =========================================================

def build_section_content(
    section: dict[str, Any],
) -> str:
    """
    Merge:

        main content
        +
        tooltip notes
        +
        action buttons

    into one self-contained retrieval unit.
    """

    parts = []

    # =====================================================
    # Main content
    # =====================================================

    content = normalize_text(
        section.get(
            "content"
        )
    )

    if content:

        parts.append(
            content
        )

    # =====================================================
    # Tooltip / supporting notes
    # =====================================================

    notes = (
        section.get(
            "notes",
            []
        )
        or []
    )

    normalized_notes = [
        normalize_text(note)
        for note in notes
        if normalize_text(note)
    ]

    if normalized_notes:

        notes_text = (
            "Additional notes:\n"
            + "\n\n".join(
                normalized_notes
            )
        )

        parts.append(
            notes_text
        )

    # =====================================================
    # Actions
    #
    # Example:
    # Apply Online
    # =====================================================

    actions = (
        section.get(
            "actions",
            []
        )
        or []
    )

    action_lines = []

    for action in actions:

        action_text = normalize_text(
            action.get(
                "text"
            )
        )

        action_url = normalize_text(
            action.get(
                "url"
            )
        )

        if (
            action_text
            and action_url
        ):

            action_lines.append(
                f"- [{action_text}]"
                f"({action_url})"
            )

        elif action_text:

            action_lines.append(
                f"- {action_text}"
            )

    if action_lines:

        parts.append(
            (
                "Actions:\n"
                + "\n".join(
                    action_lines
                )
            )
        )

    return "\n\n".join(
        parts
    )


def curate_visa_detail(
    page: dict[str, Any],
) -> list[CanonicalDocument]:
    """
    Generic country-detail curation.

    Works for:
        India
        Pakistan
        Russia
        ...
    """

    documents = []

    page_id = normalize_text(
        page.get(
            "id"
        )
    )

    country = normalize_text(
        page.get(
            "country"
        )
    )

    page_title = normalize_text(
        page.get(
            "title"
        )
    )

    url = normalize_text(
        page.get(
            "url"
        )
    )

    # =====================================================
    # 1. Visa requirement itself
    # =====================================================

    requirement = page.get(
        "visa_requirement",
        {},
    )

    requirement_content = normalize_text(
        requirement.get(
            "content"
        )
    )

    visa_required = bool(
        requirement.get(
            "required",
            False,
        )
    )

    if requirement_content:

        document = create_document(
            doc_id=(
                f"ica_"
                f"{slugify(country)}_"
                "visa_requirement"
            ),

            title=(
                f"{country} Visa Requirement"
            ),

            heading_path=(
                build_heading_path(
                    "ICA",
                    page_title,
                    "Visa Requirement",
                )
            ),

            content=(
                requirement_content
            ),

            url=url,

            metadata={
                "content_type": (
                    "visa_requirement"
                ),

                "page_type": (
                    "visa_detail"
                ),

                "country": (
                    country
                ),

                "visa_required": (
                    visa_required
                ),
            },
        )

        if document:

            documents.append(
                document
            )

    # =====================================================
    # 2. Country detail sections
    #
    # Documents Required
    # Procedure
    # Fees
    # Processing Time
    # Collection
    # =====================================================

    for index, section in enumerate(
        page.get(
            "sections",
            [],
        ),
        start=1,
    ):

        section_title = normalize_text(
            section.get(
                "title"
            )
        )

        if not section_title:
            continue

        content = build_section_content(
            section
        )

        if not content:
            continue

        document = create_document(
            doc_id=(
                f"ica_"
                f"{slugify(country)}_"
                f"{slugify(section_title)}"
            ),

            title=(
                f"{country} - "
                f"{section_title}"
            ),

            heading_path=(
                build_heading_path(
                    "ICA",
                    page_title,
                    section_title,
                )
            ),

            content=content,

            url=url,

            metadata={
                "content_type": (
                    "visa_application_section"
                ),

                "page_type": (
                    "visa_detail"
                ),

                "country": (
                    country
                ),

                "section": (
                    section_title
                ),

                "section_index": (
                    index
                ),
            },
        )

        if document:

            documents.append(
                document
            )

    return documents


# =========================================================
# VFTF
# =========================================================

def build_footnote_map(
    page: dict[str, Any],
) -> dict[str, str]:
    """
    Convert:

        [
            {"number": "1", "content": "..."},
            {"number": "2", "content": "..."}
        ]

    into:

        {
            "1": "...",
            "2": "..."
        }
    """

    result = {}

    for footnote in page.get(
        "footnotes",
        [],
    ):

        number = normalize_text(
            str(
                footnote.get(
                    "number",
                    ""
                )
            )
        )

        content = normalize_text(
            footnote.get(
                "content"
            )
        )

        if (
            number
            and content
        ):

            result[
                number
            ] = content

    return result


def infer_vftf_footnote_refs(
    group: dict[str, Any],
    footnotes: dict[str, str],
) -> list[str]:
    """
    Identify footnotes relevant to one eligibility group.

    Current source semantics:

    CIS
        -> footnote 1 defines CIS

    selected PRC nationals
        -> footnote 2 defines which PRC documents qualify

    requirement text containing [3]
        -> footnote 3 explains Single Journey Visa condition
    """

    refs = []

    title = normalize_text(
        group.get(
            "title"
        )
    )

    content = normalize_text(
        group.get(
            "content"
        )
    )

    requirements = (
        group.get(
            "requirements",
            []
        )
        or []
    )

    combined_text = (
        title
        + "\n"
        + content
        + "\n"
        + "\n".join(
            normalize_text(item)
            for item
            in requirements
        )
    )

    # =====================================================
    # Explicit [n] references still present in body text
    # =====================================================

    for number in re.findall(
        r"\[(\d+)\]",
        combined_text,
    ):

        if (
            number in footnotes
            and number not in refs
        ):

            refs.append(
                number
            )

    title_lower = (
        title.lower()
    )

    # =====================================================
    # Selected PRC definition
    # =====================================================

    if (
        "prc"
        in title_lower
        and "2"
        in footnotes
        and "2"
        not in refs
    ):

        refs.append(
            "2"
        )

    # =====================================================
    # CIS definition
    # =====================================================

    if (
        "cis"
        in title_lower
        and "1"
        in footnotes
        and "1"
        not in refs
    ):

        refs.append(
            "1"
        )

    return refs


def build_vftf_group_content(
    group: dict[str, Any],
    footnotes: dict[str, str],
) -> tuple[
    str,
    list[str],
]:
    """
    Create a self-contained VFTF eligibility document.
    """

    parts = []

    content = normalize_text(
        group.get(
            "content"
        )
    )

    if content:

        parts.append(
            content
        )

    # =====================================================
    # Requirements
    # =====================================================

    requirements = [
        normalize_text(item)
        for item in (
            group.get(
                "requirements",
                []
            )
            or []
        )
        if normalize_text(item)
    ]

    if requirements:

        requirements_text = (
            "Requirements:\n"
            + "\n".join(
                f"- {item}"
                for item
                in requirements
            )
        )

        parts.append(
            requirements_text
        )

    # =====================================================
    # Relevant footnotes
    # =====================================================

    refs = infer_vftf_footnote_refs(
        group,
        footnotes,
    )

    relevant_notes = [
        footnotes[number]
        for number in refs
        if number in footnotes
    ]

    if relevant_notes:

        parts.append(
            (
                "Relevant ICA notes:\n"
                + "\n\n".join(
                    relevant_notes
                )
            )
        )

    return (
        "\n\n".join(
            parts
        ),
        refs,
    )


def curate_vftf(
    page: dict[str, Any],
) -> list[CanonicalDocument]:
    """
    Curate:

        Visa Free Transit Facility
        ├── Overview
        ├── India + selected PRC
        └── CIS + Georgia + Turkmenistan + Ukraine

    Footnotes are attached to the relevant group,
    rather than becoming isolated documents.
    """

    documents = []

    page_id = normalize_text(
        page.get(
            "id"
        )
    )

    page_title = normalize_text(
        page.get(
            "title"
        )
    )

    url = normalize_text(
        page.get(
            "url"
        )
    )

    footnotes = (
        build_footnote_map(
            page
        )
    )

    # =====================================================
    # 1. VFTF overview
    # =====================================================

    overview = normalize_text(
        page.get(
            "overview"
        )
    )

    if overview:

        document = create_document(
            doc_id=(
                f"{page_id}_overview"
            ),

            title=(
                "Visa Free Transit Facility Overview"
            ),

            heading_path=(
                build_heading_path(
                    "ICA",
                    page_title,
                    "Overview",
                )
            ),

            content=overview,

            url=url,

            metadata={
                "content_type": (
                    "vftf_overview"
                ),

                "page_type": (
                    "vftf"
                ),
            },
        )

        if document:

            documents.append(
                document
            )

    # =====================================================
    # 2. Eligibility groups
    # =====================================================

    for index, group in enumerate(
        page.get(
            "eligibility_groups",
            [],
        ),
        start=1,
    ):

        group_title = normalize_text(
            group.get(
                "title"
            )
        )

        if not group_title:
            continue

        (
            content,
            footnote_refs,
        ) = build_vftf_group_content(
            group,
            footnotes,
        )

        if not content:
            continue

        document = create_document(
            doc_id=(
                f"{page_id}_"
                f"{slugify(group_title)}"
            ),

            title=group_title,

            heading_path=(
                build_heading_path(
                    "ICA",
                    page_title,
                    group_title,
                )
            ),

            content=content,

            url=url,

            metadata={
                "content_type": (
                    "vftf_eligibility"
                ),

                "page_type": (
                    "vftf"
                ),

                "eligibility_group": (
                    group_title
                ),

                # Chroma-friendly primitive metadata
                "footnote_refs": (
                    ",".join(
                        footnote_refs
                    )
                ),

                "group_index": (
                    index
                ),
            },
        )

        if document:

            documents.append(
                document
            )

    return documents


# =========================================================
# Page router
# =========================================================

def curate_page(
    page: dict[str, Any],
) -> list[CanonicalDocument]:
    """
    Route processed ICA page into appropriate curator.
    """

    page_type = normalize_text(
        page.get(
            "page_type"
        )
    )

    if page_type == "visa_index":

        return curate_visa_index(
            page
        )

    if page_type == "visa_detail":

        return curate_visa_detail(
            page
        )

    if page_type == "vftf":

        return curate_vftf(
            page
        )

    return []


# =========================================================
# Load processed files
# =========================================================

def load_processed_pages() -> list[dict[str, Any]]:
    """
    Load valid processed ICA page JSONs.

    extraction_report.json is ignored automatically
    because it does not contain page_type.
    """

    if not PROCESSED_DIR.exists():

        raise FileNotFoundError(
            f"Processed directory not found: "
            f"{PROCESSED_DIR}"
        )

    pages = []

    for path in sorted(
        PROCESSED_DIR.glob(
            "*.json"
        )
    ):

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            data,
            dict,
        ):
            continue

        if data.get(
            "page_type"
        ) not in {
            "visa_index",
            "visa_detail",
            "vftf",
        }:
            continue

        pages.append(
            data
        )

    return pages


# =========================================================
# Save
# =========================================================

def save_jsonl(
    documents: list[CanonicalDocument],
) -> None:

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        for document in documents:

            file.write(
                json.dumps(
                    document.model_dump(),
                    ensure_ascii=False,
                )
            )

            file.write(
                "\n"
            )


# =========================================================
# Main
# =========================================================

def main() -> None:

    pages = (
        load_processed_pages()
    )

    if not pages:

        raise ValueError(
            "No processed ICA pages found."
        )

    documents = []

    for page in pages:

        page_documents = curate_page(
            page
        )

        documents.extend(
            page_documents
        )

        print(
            f"{page.get('id')}: "
            f"{len(page_documents)} documents"
        )

    save_jsonl(
        documents
    )

    # =====================================================
    # Summary
    # =====================================================

    content_type_counts = {}

    for document in documents:

        content_type = (
            document.metadata.get(
                "content_type",
                "unknown",
            )
        )

        content_type_counts[
            content_type
        ] = (
            content_type_counts.get(
                content_type,
                0,
            )
            + 1
        )

    print(
        "\nICA curation completed."
    )

    print(
        f"Processed pages: "
        f"{len(pages)}"
    )

    print(
        f"Canonical documents: "
        f"{len(documents)}"
    )

    print(
        f"Output: "
        f"{OUTPUT_PATH}"
    )

    print(
        "\nContent types:"
    )

    for (
        content_type,
        count,
    ) in sorted(
        content_type_counts.items()
    ):

        print(
            f"  {content_type}: "
            f"{count}"
        )


if __name__ == "__main__":
    main()