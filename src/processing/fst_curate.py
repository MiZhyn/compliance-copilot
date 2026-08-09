import json
import re

from collections import Counter
from pathlib import Path
from typing import Any

from src.models.document import CanonicalDocument


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_FST_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "fst"
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

DOCUMENT_OUTPUT = (
    CURATED_DIR
    / "fst_documents.jsonl"
)

ASSET_OUTPUT = (
    CURATED_DIR
    / "fst_assets.jsonl"
)


# =========================================================
# Text utilities
# =========================================================

def normalize_text(
    text: str | None,
) -> str:
    """
    Light normalization for final knowledge content.

    Preserve paragraph structure while removing:
    - invisible characters
    - leaked AEM template blocks
    - excessive whitespace
    """

    if not text:
        return ""

    text = str(text)

    text = text.replace(
        "\xa0",
        " ",
    )

    text = re.sub(
        r"[\u200b\u200c\u200d\ufeff]",
        "",
        text,
    )

    # Fallback cleaning in case AEM markup leaked
    # from extraction.
    text = re.sub(
        r"<sly\b[^>]*>.*?</sly>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<template\b[^>]*>.*?</template>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r" *\n *",
        "\n",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def comparison_text(
    text: str | None,
) -> str:
    """
    Normalized comparison form used for:
    - exact deduplication
    - overlap checking
    - structured-content filtering

    Not used as user-facing document content.
    """

    text = normalize_text(
        text
    )

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def heading_path_to_string(
    heading_path: list[str] | None,
) -> str | None:
    """
    Convert:

        [
            "City Sights Tour",
            "Tour Itinerary",
            "Merlion Park"
        ]

    to:

        City Sights Tour > Tour Itinerary > Merlion Park
    """

    if not heading_path:
        return None

    cleaned = []

    for heading in heading_path:

        heading = normalize_text(
            heading
        )

        if not heading:
            continue

        if (
            cleaned
            and comparison_text(
                cleaned[-1]
            )
            == comparison_text(
                heading
            )
        ):
            continue

        cleaned.append(
            heading
        )

    if not cleaned:
        return None

    return " > ".join(
        cleaned
    )


def ensure_page_in_heading_path(
    page: dict[str, Any],
    heading_path: list[str],
) -> list[str]:
    """
    Ensure every heading path starts with page title.
    """

    page_title = normalize_text(
        page.get(
            "title",
            page.get(
                "name",
                "",
            ),
        )
    )

    cleaned = [
        normalize_text(
            value
        )
        for value in heading_path
        if normalize_text(
            value
        )
    ]

    if not page_title:
        return cleaned

    if not cleaned:
        return [
            page_title
        ]

    if (
        comparison_text(
            cleaned[0]
        )
        != comparison_text(
            page_title
        )
    ):
        cleaned.insert(
            0,
            page_title,
        )

    return cleaned


def clean_accordion_title(
    title: str,
) -> str:
    """
    Remove visual FAQ numbering.

    Example:

        3. What do I need to join the tour?

    becomes:

        What do I need to join the tour?
    """

    title = normalize_text(
        title
    )

    return re.sub(
        r"^\d+\.\s*",
        "",
        title,
    )


# =========================================================
# Asset registry
# =========================================================

def build_image_assets(
    page: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Create one image asset registry per page.

    Key design:

    - generic extracted images are preserved
    - itinerary image relationships are enriched from
      page["itineraries"]
    - ALT is stored only as image metadata
    - itinerary visible title is authoritative
    """

    assets = []

    url_to_asset = {}

    # =====================================================
    # 1. Generic extracted images
    # =====================================================

    for image in page.get(
        "images",
        [],
    ):

        url = normalize_text(
            image.get(
                "url"
            )
        )

        if not url:
            continue

        # Prevent duplicate URLs
        if url in url_to_asset:
            continue

        asset_id = (
            f"fst_{page['id']}"
            f"_img_{len(assets) + 1:03d}"
        )

        nearby_heading = normalize_text(
            image.get(
                "nearby_heading"
            )
        )

        nearby_text = normalize_text(
            image.get(
                "nearby_text"
            )
        )

        alt = normalize_text(
            image.get(
                "alt"
            )
        )

        asset = {
            "asset_id": asset_id,

            "asset_type": "image",

            "source": "Changi Airport",

            "page_id": page["id"],

            "page_title": page.get(
                "title",
                page.get(
                    "name",
                    "",
                ),
            ),

            "source_url": page.get(
                "url"
            ),

            "url": url,

            # IMPORTANT:
            # Do not use alt as semantic title.
            "title": nearby_heading,

            "alt": alt,

            "nearby_heading": (
                nearby_heading
            ),

            "nearby_text": (
                nearby_text
            ),

            "roles": [
                "generic"
            ],

            "itinerary_titles": [],
        }

        assets.append(
            asset
        )

        url_to_asset[
            url
        ] = asset

    # =====================================================
    # 2. Enrich itinerary images using authoritative
    #    itinerary structure
    # =====================================================

    for itinerary in page.get(
        "itineraries",
        [],
    ):

        image = (
            itinerary.get(
                "image"
            )
            or {}
        )

        url = normalize_text(
            image.get(
                "url"
            )
        )

        if not url:
            continue

        itinerary_title = normalize_text(
            itinerary.get(
                "title"
            )
        )

        description = normalize_text(
            itinerary.get(
                "description"
            )
        )

        alt = normalize_text(
            image.get(
                "alt"
            )
        )

        # -----------------------------------------
        # Existing generic asset
        # -----------------------------------------

        if url in url_to_asset:

            asset = url_to_asset[
                url
            ]

        # -----------------------------------------
        # Itinerary image was not captured in
        # generic image extraction
        # -----------------------------------------

        else:

            asset_id = (
                f"fst_{page['id']}"
                f"_img_{len(assets) + 1:03d}"
            )

            asset = {
                "asset_id": asset_id,

                "asset_type": "image",

                "source": (
                    "Changi Airport"
                ),

                "page_id": page[
                    "id"
                ],

                "page_title": page.get(
                    "title",
                    page.get(
                        "name",
                        "",
                    ),
                ),

                "source_url": page.get(
                    "url"
                ),

                "url": url,

                "title": "",

                "alt": alt,

                "nearby_heading": "",

                "nearby_text": "",

                "roles": [],

                "itinerary_titles": [],
            }

            assets.append(
                asset
            )

            url_to_asset[
                url
            ] = asset

        # -----------------------------------------
        # Itinerary is authoritative for title
        # -----------------------------------------

        if "itinerary" not in asset[
            "roles"
        ]:
            asset[
                "roles"
            ].append(
                "itinerary"
            )

        if (
            itinerary_title
            and itinerary_title
            not in asset[
                "itinerary_titles"
            ]
        ):

            asset[
                "itinerary_titles"
            ].append(
                itinerary_title
            )

        if itinerary_title:

            asset[
                "title"
            ] = itinerary_title

        if description:

            asset[
                "nearby_text"
            ] = description

        if alt:

            asset[
                "alt"
            ] = alt

    return assets


def get_asset_id_by_url(
    url: str,
    assets: list[dict[str, Any]],
) -> str | None:

    url = normalize_text(
        url
    )

    if not url:
        return None

    for asset in assets:

        if normalize_text(
            asset.get(
                "url"
            )
        ) == url:

            return asset[
                "asset_id"
            ]

    return None


def find_related_assets(
    content: str,
    assets: list[dict[str, Any]],
) -> list[str]:
    """
    Fallback relationship matcher for generic content.

    Structured components such as itineraries should
    provide asset_ids explicitly instead.
    """

    content_cmp = comparison_text(
        content
    )

    if not content_cmp:
        return []

    matched = []

    for asset in assets:

        nearby_text = comparison_text(
            asset.get(
                "nearby_text"
            )
        )

        if not nearby_text:
            continue

        if (
            nearby_text in content_cmp
            or content_cmp in nearby_text
        ):

            matched.append(
                asset[
                    "asset_id"
                ]
            )

    return list(
        dict.fromkeys(
            matched
        )
    )


# =========================================================
# Canonical document creation
# =========================================================

def create_document(
    *,
    page: dict[str, Any],
    doc_id: str,
    heading_path: list[str],
    content: str,
    content_type: str,
    assets: list[dict[str, Any]],
    asset_ids: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> CanonicalDocument:
    """
    Convert curated content into common
    CanonicalDocument format.
    """

    content = normalize_text(
        content
    )

    # Structured component can provide exact relation.
    if asset_ids is None:

        resolved_asset_ids = (
            find_related_assets(
                content,
                assets,
            )
        )

    else:

        resolved_asset_ids = list(
            dict.fromkeys(
                [
                    value
                    for value in asset_ids
                    if value
                ]
            )
        )

    metadata = {
        "page_id": page[
            "id"
        ],

        "page_type": page.get(
            "page_type",
            "tour",
        ),

        "content_type": (
            content_type
        ),

        "asset_ids": (
            resolved_asset_ids
        ),
    }

    if extra_metadata:

        metadata.update(
            extra_metadata
        )

    return CanonicalDocument(
        doc_id=doc_id,

        source="Changi Airport",

        source_type="web",

        title=page.get(
            "title",
            page.get(
                "name",
                "",
            ),
        ),

        heading_path=(
            heading_path_to_string(
                ensure_page_in_heading_path(
                    page,
                    heading_path,
                )
            )
        ),

        content=content,

        url=page.get(
            "url"
        ),

        metadata=metadata,
    )


# =========================================================
# Registration Details
# =========================================================

def curate_registration_details(
    page: dict[str, Any],
    assets: list[dict[str, Any]],
) -> list[CanonicalDocument]:
    """
    Convert:

        Registration Details
            Service Counters
            Required Documents

    directly into semantic documents.

    No heading inference is required anymore.
    """

    registration = (
        page.get(
            "registration_details"
        )
        or {}
    )

    if not registration:
        return []

    parent_title = normalize_text(
        registration.get(
            "title"
        )
    )

    if not parent_title:
        parent_title = (
            "Registration Details"
        )

    documents = []

    for index, subsection in enumerate(
        registration.get(
            "subsections",
            [],
        ),
        start=1,
    ):

        subsection_title = normalize_text(
            subsection.get(
                "title"
            )
        )

        if not subsection_title:
            subsection_title = (
                f"Registration Detail {index}"
            )

        content_parts = []

        intro = normalize_text(
            subsection.get(
                "content"
            )
        )

        if intro:

            content_parts.append(
                intro
            )

        # -----------------------------------------
        # Structured bullet items
        # -----------------------------------------

        for item in subsection.get(
            "items",
            [],
        ):

            label = normalize_text(
                item.get(
                    "label"
                )
            )

            item_content = normalize_text(
                item.get(
                    "content"
                )
            )

            if (
                label
                and item_content
            ):

                content_parts.append(
                    f"{label}: "
                    f"{item_content}"
                )

            elif item_content:

                content_parts.append(
                    item_content
                )

        content = "\n".join(
            content_parts
        )

        if not content:
            continue

        documents.append(
            create_document(
                page=page,

                doc_id=(
                    f"fst_{page['id']}"
                    f"_registration_"
                    f"{index:03d}"
                ),

                heading_path=[
                    parent_title,
                    subsection_title,
                ],

                content=content,

                content_type=(
                    "registration_detail"
                ),

                assets=assets,

                asset_ids=[],

                extra_metadata={
                    "registration_section": (
                        subsection_title
                    ),
                },
            )
        )

    return documents


# =========================================================
# Itineraries
# =========================================================

def curate_itineraries(
    page: dict[str, Any],
    assets: list[dict[str, Any]],
) -> list[CanonicalDocument]:
    """
    Directly curate structured itinerary cards.

    IMPORTANT:
    itinerary["title"] comes from visible DOM title.
    ALT is never used as itinerary title.
    """

    documents = []

    for index, itinerary in enumerate(
        page.get(
            "itineraries",
            [],
        ),
        start=1,
    ):

        title = normalize_text(
            itinerary.get(
                "title"
            )
        )

        description = normalize_text(
            itinerary.get(
                "description"
            )
        )

        if not title and not description:
            continue

        if not title:
            title = (
                f"Tour Stop {index}"
            )

        # CanonicalDocument content cannot be empty.
        content = (
            description
            or title
        )

        image = (
            itinerary.get(
                "image"
            )
            or {}
        )

        image_url = normalize_text(
            image.get(
                "url"
            )
        )

        primary_asset_id = (
            get_asset_id_by_url(
                image_url,
                assets,
            )
        )

        asset_ids = []

        if primary_asset_id:

            asset_ids.append(
                primary_asset_id
            )

        metadata = {
            "itinerary_title": title,

            "itinerary_index": (
                itinerary.get(
                    "index",
                    index,
                )
            ),

            "source_component": (
                itinerary.get(
                    "source_component"
                )
            ),

            "slider_index": (
                itinerary.get(
                    "slider_index"
                )
            ),

            "slide_index": (
                itinerary.get(
                    "slide_index"
                )
            ),

            "primary_asset_id": (
                primary_asset_id
            ),
        }

        documents.append(
            create_document(
                page=page,

                doc_id=(
                    f"fst_{page['id']}"
                    f"_itinerary_"
                    f"{index:03d}"
                ),

                heading_path=[
                    "Tour Itinerary",
                    title,
                ],

                content=content,

                content_type=(
                    "itinerary"
                ),

                assets=assets,

                asset_ids=(
                    asset_ids
                ),

                extra_metadata=(
                    metadata
                ),
            )
        )

    return documents


# =========================================================
# Table curation
# =========================================================

def normalize_table(
    table: dict[str, Any],
) -> tuple[
    list[str],
    list[list[str]],
]:
    """
    Normalize table structure.

    CAG tables sometimes have no <th>.
    In that case, the first row is treated as header.
    """

    headers = [
        normalize_text(
            value
        )
        for value in table.get(
            "headers",
            [],
        )
    ]

    rows = [
        [
            normalize_text(
                value
            )
            for value in row
        ]
        for row in table.get(
            "rows",
            [],
        )
    ]

    rows = [
        row
        for row in rows
        if any(
            row
        )
    ]

    if (
        not headers
        and len(rows) >= 2
    ):

        headers = rows[0]

        rows = rows[
            1:
        ]

    return (
        headers,
        rows,
    )


def table_to_markdown(
    headers: list[str],
    rows: list[list[str]],
) -> str:

    lines = []

    if headers:

        lines.append(
            " | ".join(
                headers
            )
        )

        lines.append(
            " | ".join(
                ["---"]
                * len(
                    headers
                )
            )
        )

    for row in rows:

        lines.append(
            " | ".join(
                row
            )
        )

    return "\n".join(
        lines
    )


def infer_table_heading(
    table: dict[str, Any],
    headers: list[str],
) -> str:
    """
    Infer business-friendly heading from table structure.

    This is based on column semantics, not page names.
    """

    header_cmp = comparison_text(
        " ".join(
            headers
        )
    )

    schedule_terms = [
        "reporting time",
        "tour timing",
        "flight departure",
        "tour itinerary",
    ]

    if any(
        term in header_cmp
        for term in schedule_terms
    ):

        return "Tour Schedule"

    caption = normalize_text(
        table.get(
            "caption"
        )
    )

    return (
        caption
        or "Table"
    )


def curate_table_list(
    *,
    page: dict[str, Any],
    tables: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    id_prefix: str,
    heading_prefix: list[str],
    extra_metadata: dict[str, Any] | None = None,
) -> list[CanonicalDocument]:

    documents = []

    for index, table in enumerate(
        tables,
        start=1,
    ):

        (
            headers,
            rows,
        ) = normalize_table(
            table
        )

        content = table_to_markdown(
            headers,
            rows,
        )

        notes = [
            normalize_text(
                note
            )
            for note in table.get(
                "notes",
                [],
            )
            if normalize_text(
                note
            )
        ]

        # -----------------------------------------
        # Important schedule notes belong with table
        # -----------------------------------------

        if notes:

            note_text = "\n".join(
                f"- {note}"
                for note in notes
            )

            if content:

                content += (
                    "\n\nNotes:\n"
                    + note_text
                )

            else:

                content = (
                    "Notes:\n"
                    + note_text
                )

        if not content:
            continue

        table_heading = (
            infer_table_heading(
                table,
                headers,
            )
        )

        metadata = {
            "table_caption": (
                table.get(
                    "caption"
                )
            ),

            "table_notes": (
                notes
            ),
        }

        if extra_metadata:

            metadata.update(
                extra_metadata
            )

        documents.append(
            create_document(
                page=page,

                doc_id=(
                    f"{id_prefix}"
                    f"_{index:03d}"
                ),

                heading_path=(
                    heading_prefix
                    + [
                        table_heading
                    ]
                ),

                content=content,

                content_type="table",

                assets=assets,

                asset_ids=[],

                extra_metadata=(
                    metadata
                ),
            )
        )

    return documents


def curate_tables(
    page: dict[str, Any],
    assets: list[dict[str, Any]],
) -> list[CanonicalDocument]:

    return curate_table_list(
        page=page,

        tables=page.get(
            "tables",
            [],
        ),

        assets=assets,

        id_prefix=(
            f"fst_{page['id']}"
            f"_table"
        ),

        heading_prefix=[],
    )


# =========================================================
# Accordion / FAQ curation
# =========================================================

def curate_accordion_list(
    *,
    page: dict[str, Any],
    accordions: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    id_prefix: str,
    context_heading: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> list[CanonicalDocument]:

    documents = []

    context_heading = (
        context_heading
        or []
    )

    for index, accordion in enumerate(
        accordions,
        start=1,
    ):

        content = normalize_text(
            accordion.get(
                "content"
            )
        )

        if not content:
            continue

        question = (
            clean_accordion_title(
                accordion.get(
                    "title",
                    "",
                )
            )
        )

        original_path = [
            normalize_text(
                heading
            )
            for heading in accordion.get(
                "heading_path",
                [],
            )
            if normalize_text(
                heading
            )
        ]

        # Clean numbering from final FAQ heading
        if original_path:

            original_path[
                -1
            ] = clean_accordion_title(
                original_path[
                    -1
                ]
            )

        if not original_path:

            original_path = [
                question
            ]

        heading_path = (
            context_heading
            + original_path
        )

        metadata = {
            "question": (
                question
            ),
        }

        if extra_metadata:

            metadata.update(
                extra_metadata
            )

        documents.append(
            create_document(
                page=page,

                doc_id=(
                    f"{id_prefix}"
                    f"_{index:03d}"
                ),

                heading_path=(
                    heading_path
                ),

                content=content,

                content_type="faq",

                assets=assets,

                asset_ids=[],

                extra_metadata=(
                    metadata
                ),
            )
        )

    return documents


def curate_accordions(
    page: dict[str, Any],
    assets: list[dict[str, Any]],
) -> list[CanonicalDocument]:

    return curate_accordion_list(
        page=page,

        accordions=page.get(
            "accordions",
            [],
        ),

        assets=assets,

        id_prefix=(
            f"fst_{page['id']}"
            f"_faq"
        ),
    )


# =========================================================
# Tab curation
# =========================================================

def curate_tabs(
    page: dict[str, Any],
    assets: list[dict[str, Any]],
) -> list[CanonicalDocument]:
    """
    Support both:
    - richer old tab extraction
    - simpler new tab extraction
    """

    documents = []

    for tab_index, tab in enumerate(
        page.get(
            "tabs",
            [],
        ),
        start=1,
    ):

        tab_title = normalize_text(
            tab.get(
                "title"
            )
        )

        if not tab_title:

            tab_title = (
                f"Tab {tab_index}"
            )

        tab_sections = tab.get(
            "sections",
            [],
        )

        tab_accordions = tab.get(
            "accordions",
            [],
        )

        tab_tables = tab.get(
            "tables",
            [],
        )

        # =================================================
        # Rich structured sections
        # =================================================

        for section_index, section in enumerate(
            tab_sections,
            start=1,
        ):

            content_items = [
                normalize_text(
                    item
                )
                for item
                in section.get(
                    "content",
                    [],
                )
                if normalize_text(
                    item
                )
            ]

            content = "\n\n".join(
                content_items
            )

            if not content:
                continue

            heading_path = (
                section.get(
                    "heading_path"
                )
                or [
                    tab_title
                ]
            )

            documents.append(
                create_document(
                    page=page,

                    doc_id=(
                        f"fst_{page['id']}"
                        f"_tab_{tab_index:03d}"
                        f"_section_"
                        f"{section_index:03d}"
                    ),

                    heading_path=(
                        heading_path
                    ),

                    content=content,

                    content_type=(
                        "tab_section"
                    ),

                    assets=assets,

                    extra_metadata={
                        "tab_title": (
                            tab_title
                        ),
                    },
                )
            )

        # =================================================
        # Simple tab body
        #
        # Only create when no richer child structure exists,
        # avoiding obvious duplication.
        # =================================================

        if (
            not tab_sections
            and not tab_accordions
            and not tab_tables
        ):

            tab_content = normalize_text(
                tab.get(
                    "content"
                )
            )

            if tab_content:

                documents.append(
                    create_document(
                        page=page,

                        doc_id=(
                            f"fst_{page['id']}"
                            f"_tab_{tab_index:03d}"
                        ),

                        heading_path=[
                            tab_title
                        ],

                        content=(
                            tab_content
                        ),

                        content_type=(
                            "tab_section"
                        ),

                        assets=assets,

                        extra_metadata={
                            "tab_title": (
                                tab_title
                            ),
                        },
                    )
                )

        # =================================================
        # Tab accordions
        # =================================================

        documents.extend(
            curate_accordion_list(
                page=page,

                accordions=(
                    tab_accordions
                ),

                assets=assets,

                id_prefix=(
                    f"fst_{page['id']}"
                    f"_tab_{tab_index:03d}"
                    f"_faq"
                ),

                context_heading=[
                    tab_title
                ],

                extra_metadata={
                    "tab_title": (
                        tab_title
                    ),
                },
            )
        )

        # =================================================
        # Tab tables
        # =================================================

        documents.extend(
            curate_table_list(
                page=page,

                tables=(
                    tab_tables
                ),

                assets=assets,

                id_prefix=(
                    f"fst_{page['id']}"
                    f"_tab_{tab_index:03d}"
                    f"_table"
                ),

                heading_prefix=[
                    tab_title
                ],

                extra_metadata={
                    "tab_title": (
                        tab_title
                    ),
                },
            )
        )

        # =================================================
        # Optional richer old location directory support
        # =================================================

        location_directory = (
            tab.get(
                "location_directory"
            )
            or {}
        )

        for location_index, location in enumerate(
            location_directory.get(
                "locations",
                [],
            ),
            start=1,
        ):

            fields = []

            mapping = [
                (
                    "Location",
                    "location_name",
                ),
                (
                    "Level",
                    "level",
                ),
                (
                    "Details",
                    "details",
                ),
                (
                    "Phone",
                    "phone",
                ),
                (
                    "Operating status",
                    "operating_status",
                ),
                (
                    "Operating time",
                    "operating_time",
                ),
                (
                    "Operating days",
                    "operating_days",
                ),
            ]

            for label, field_name in mapping:

                value = normalize_text(
                    location.get(
                        field_name
                    )
                )

                if value:

                    fields.append(
                        f"{label}: "
                        f"{value}"
                    )

            content = "\n".join(
                fields
            )

            if not content:
                continue

            documents.append(
                create_document(
                    page=page,

                    doc_id=(
                        f"fst_{page['id']}"
                        f"_tab_{tab_index:03d}"
                        f"_location_"
                        f"{location_index:03d}"
                    ),

                    heading_path=[
                        tab_title,
                        location.get(
                            "location_name",
                            "Location",
                        ),
                    ],

                    content=content,

                    content_type=(
                        "location"
                    ),

                    assets=assets,

                    asset_ids=[],

                    extra_metadata={
                        "tab_title": (
                            tab_title
                        ),

                        "map_url": (
                            location.get(
                                "map_url"
                            )
                        ),
                    },
                )
            )

    return documents


# =========================================================
# Structured coverage
# =========================================================

def collect_structured_coverage(
    page: dict[str, Any],
) -> list[str]:
    """
    Build a normalized set of content already represented
    by structured components.

    This prevents generic sections from producing duplicate
    documents for:

    - registration details
    - itinerary descriptions
    - schedule notes
    - accordions
    - tabs
    """

    coverage = []

    def add(
        text: str | None,
    ) -> None:

        value = comparison_text(
            text
        )

        if value:

            coverage.append(
                value
            )

    # =====================================================
    # Registration
    # =====================================================

    registration = (
        page.get(
            "registration_details"
        )
        or {}
    )

    for subsection in registration.get(
        "subsections",
        [],
    ):

        title = normalize_text(
            subsection.get(
                "title"
            )
        )

        content = normalize_text(
            subsection.get(
                "content"
            )
        )

        add(
            content
        )

        if title and content:

            add(
                f"{title} "
                f"{content}"
            )

        for item in subsection.get(
            "items",
            [],
        ):

            label = normalize_text(
                item.get(
                    "label"
                )
            )

            item_content = normalize_text(
                item.get(
                    "content"
                )
            )

            add(
                item_content
            )

            if label and item_content:

                add(
                    f"{label}: "
                    f"{item_content}"
                )

    # =====================================================
    # Itineraries
    # =====================================================

    for itinerary in page.get(
        "itineraries",
        [],
    ):

        title = normalize_text(
            itinerary.get(
                "title"
            )
        )

        description = normalize_text(
            itinerary.get(
                "description"
            )
        )

        add(
            description
        )

        if title and description:

            add(
                f"{title} "
                f"{description}"
            )

    # =====================================================
    # Table notes
    # =====================================================

    for table in page.get(
        "tables",
        [],
    ):

        for note in table.get(
            "notes",
            [],
        ):

            add(
                note
            )

    # =====================================================
    # Accordions
    # =====================================================

    for accordion in page.get(
        "accordions",
        [],
    ):

        title = normalize_text(
            accordion.get(
                "title"
            )
        )

        content = normalize_text(
            accordion.get(
                "content"
            )
        )

        add(
            content
        )

        if title and content:

            add(
                f"{title} "
                f"{content}"
            )

    # =====================================================
    # Tabs
    # =====================================================

    for tab in page.get(
        "tabs",
        [],
    ):

        add(
            tab.get(
                "content"
            )
        )

        for accordion in tab.get(
            "accordions",
            [],
        ):

            add(
                accordion.get(
                    "content"
                )
            )

        for table in tab.get(
            "tables",
            [],
        ):

            for note in table.get(
                "notes",
                [],
            ):

                add(
                    note
                )

    return list(
        dict.fromkeys(
            coverage
        )
    )


def is_covered_by_structured_content(
    text: str,
    coverage: list[str],
) -> bool:
    """
    Determine whether a section paragraph has already
    been represented by a structured component.

    We use:
    - exact normalized match
    - sufficiently long containment

    Long-text threshold prevents short generic phrases
    from causing false removals.
    """

    text_cmp = comparison_text(
        text
    )

    if not text_cmp:
        return True

    for structured_cmp in coverage:

        # Exact match
        if text_cmp == structured_cmp:

            return True

        # Containment only for meaningful longer text
        if (
            len(
                text_cmp
            ) >= 35
            and text_cmp
            in structured_cmp
        ):

            return True

        if (
            len(
                structured_cmp
            ) >= 35
            and structured_cmp
            in text_cmp
        ):

            return True

    return False


# =========================================================
# Service notices
# =========================================================

def is_service_notice(
    text: str,
) -> bool:
    """
    Temporary operational notice detection.

    This remains in curation because it is semantic
    classification rather than DOM reconstruction.
    """

    text_cmp = comparison_text(
        text
    )

    keywords = [
        "scheduled maintenance",
        "temporarily unavailable",
        "resume on",
        "we apologise",
        "we apologize",
        "currently unavailable",
    ]

    return any(
        keyword in text_cmp
        for keyword in keywords
    )


# =========================================================
# Generic section curation
# =========================================================

def curate_sections(
    page: dict[str, Any],
    assets: list[dict[str, Any]],
) -> list[CanonicalDocument]:
    """
    Curate only RESIDUAL generic content.

    Structured information is removed first.

    Therefore this function no longer needs:
    - INLINE_SECTION_HEADINGS
    - registration state machine
    - itinerary image matching
    - ALT-based title inference
    """

    documents = []

    coverage = (
        collect_structured_coverage(
            page
        )
    )

    doc_counter = 0

    page_title = normalize_text(
        page.get(
            "title",
            page.get(
                "name",
                "",
            ),
        )
    )

    for section in page.get(
        "sections",
        [],
    ):

        raw_paragraphs = [
            normalize_text(
                paragraph
            )
            for paragraph in section.get(
                "content",
                [],
            )
            if normalize_text(
                paragraph
            )
        ]

        # -----------------------------------------
        # Remove content already represented by
        # structured components
        # -----------------------------------------

        paragraphs = [
            paragraph
            for paragraph
            in raw_paragraphs
            if not (
                is_covered_by_structured_content(
                    paragraph,
                    coverage,
                )
            )
        ]

        if not paragraphs:
            continue

        section_heading = normalize_text(
            section.get(
                "heading"
            )
        )

        original_heading_path = [
            normalize_text(
                value
            )
            for value
            in section.get(
                "heading_path",
                [],
            )
            if normalize_text(
                value
            )
        ]

        # =========================================
        # Determine generic section type
        # =========================================

        if (
            not section_heading
            or comparison_text(
                section_heading
            )
            == comparison_text(
                page_title
            )
        ):

            generic_content_type = (
                "overview"
            )

            generic_heading_path = [
                "Overview"
            ]

        else:

            generic_content_type = (
                "section"
            )

            generic_heading_path = (
                original_heading_path
                or [
                    section_heading
                ]
            )

        overview_buffer = []

        notice_buffer = []

        # =========================================
        # Flush helpers
        # =========================================

        def save_generic() -> None:

            nonlocal doc_counter
            nonlocal overview_buffer

            if not overview_buffer:
                return

            content = "\n\n".join(
                overview_buffer
            )

            doc_counter += 1

            documents.append(
                create_document(
                    page=page,

                    doc_id=(
                        f"fst_{page['id']}"
                        f"_section_"
                        f"{doc_counter:03d}"
                    ),

                    heading_path=(
                        generic_heading_path
                    ),

                    content=content,

                    content_type=(
                        generic_content_type
                    ),

                    assets=assets,
                )
            )

            overview_buffer = []

        def save_notice() -> None:

            nonlocal doc_counter
            nonlocal notice_buffer

            if not notice_buffer:
                return

            content = "\n\n".join(
                notice_buffer
            )

            doc_counter += 1

            documents.append(
                create_document(
                    page=page,

                    doc_id=(
                        f"fst_{page['id']}"
                        f"_notice_"
                        f"{doc_counter:03d}"
                    ),

                    heading_path=[
                        "Service Notice"
                    ],

                    content=content,

                    content_type=(
                        "service_notice"
                    ),

                    assets=assets,

                    asset_ids=[],

                    extra_metadata={
                        "time_sensitive": (
                            True
                        ),
                    },
                )
            )

            notice_buffer = []

        # =========================================
        # Walk residual content
        # =========================================

        for paragraph in paragraphs:

            if is_service_notice(
                paragraph
            ):

                # Close normal content first.
                save_generic()

                notice_buffer.append(
                    paragraph
                )

                continue

            # If previous paragraph(s) were notice,
            # close notice before returning to normal text.
            if notice_buffer:

                save_notice()

            overview_buffer.append(
                paragraph
            )

        save_generic()
        save_notice()

    return documents


# =========================================================
# Page curation
# =========================================================

def curate_page(
    page: dict[str, Any],
) -> tuple[
    list[CanonicalDocument],
    list[dict[str, Any]],
]:
    """
    Curate one FST page.

    Extraction has already identified the source structure.

    Curation maps each structure into the canonical
    knowledge model.
    """

    assets = build_image_assets(
        page
    )

    documents = []

    # =====================================================
    # 1. Residual/general content
    # =====================================================

    documents.extend(
        curate_sections(
            page,
            assets,
        )
    )

    # =====================================================
    # 2. Registration
    # =====================================================

    documents.extend(
        curate_registration_details(
            page,
            assets,
        )
    )

    # =====================================================
    # 3. Tour schedule / other tables
    # =====================================================

    documents.extend(
        curate_tables(
            page,
            assets,
        )
    )

    # =====================================================
    # 4. Structured itinerary
    # =====================================================

    documents.extend(
        curate_itineraries(
            page,
            assets,
        )
    )

    # =====================================================
    # 5. FAQ
    # =====================================================

    documents.extend(
        curate_accordions(
            page,
            assets,
        )
    )

    # =====================================================
    # 6. Tabs
    # =====================================================

    documents.extend(
        curate_tabs(
            page,
            assets,
        )
    )

    return (
        documents,
        assets,
    )


# =========================================================
# Deduplication
# =========================================================

CONTENT_TYPE_PRIORITY = {
    "itinerary": 100,
    "registration_detail": 95,
    "faq": 90,
    "table": 85,
    "service_notice": 80,
    "location": 75,
    "tab_section": 60,
    "section": 40,
    "overview": 30,
}


def document_priority(
    document: CanonicalDocument,
) -> int:
    """
    When exact duplicate content exists, prefer
    the more structured / specific representation.
    """

    content_type = (
        document.metadata.get(
            "content_type",
            "",
        )
    )

    score = (
        CONTENT_TYPE_PRIORITY.get(
            content_type,
            0,
        )
    )

    # Prefer dedicated tour detail page over the
    # general FST landing page when content is identical.
    if (
        document.metadata.get(
            "page_id"
        )
        != "free_sg_tour"
    ):

        score += 5

    return score


def deduplicate_documents(
    documents: list[CanonicalDocument],
) -> list[CanonicalDocument]:
    """
    Exact normalized deduplication.

    If duplicate content exists, keep the higher-priority
    structured document.

    No semantic embedding-based deduplication yet.
    """

    selected = {}

    order = []

    for document in documents:

        key = comparison_text(
            document.content
        )

        if not key:
            continue

        if key not in selected:

            selected[
                key
            ] = document

            order.append(
                key
            )

            continue

        current = selected[
            key
        ]

        if (
            document_priority(
                document
            )
            > document_priority(
                current
            )
        ):

            selected[
                key
            ] = document

    return [
        selected[
            key
        ]
        for key in order
    ]


def deduplicate_assets(
    assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Deduplicate assets by asset_id.
    """

    unique = []

    seen = set()

    for asset in assets:

        asset_id = asset[
            "asset_id"
        ]

        if asset_id in seen:
            continue

        seen.add(
            asset_id
        )

        unique.append(
            asset
        )

    return unique


# =========================================================
# JSONL
# =========================================================

def save_jsonl(
    records: list,
    output_path: Path,
) -> None:

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:

            if isinstance(
                record,
                CanonicalDocument,
            ):

                data = (
                    record.model_dump()
                )

            else:

                data = record

            file.write(
                json.dumps(
                    data,
                    ensure_ascii=False,
                )
                + "\n"
            )


# =========================================================
# Main
# =========================================================

def main() -> None:

    all_documents = []

    all_assets = []

    input_files = sorted(
        PROCESSED_FST_DIR.glob(
            "*.json"
        )
    )

    if not input_files:

        raise FileNotFoundError(
            "No processed FST JSON files found in: "
            f"{PROCESSED_FST_DIR}"
        )

    for input_file in input_files:

        # Skip extraction report
        if (
            "report"
            in input_file.name.lower()
        ):
            continue

        print(
            f"\nCurating: "
            f"{input_file.name}"
        )

        page = json.loads(
            input_file.read_text(
                encoding="utf-8"
            )
        )

        (
            documents,
            assets,
        ) = curate_page(
            page
        )

        all_documents.extend(
            documents
        )

        all_assets.extend(
            assets
        )

        page_type_counts = Counter(
            document.metadata.get(
                "content_type",
                "unknown",
            )
            for document
            in documents
        )

        print(
            f"  Documents created: "
            f"{len(documents)}"
        )

        print(
            f"  Image assets: "
            f"{len(assets)}"
        )

        print(
            "  Content types:",
            dict(
                page_type_counts
            ),
        )

    # =====================================================
    # Global deduplication
    # =====================================================

    all_documents = (
        deduplicate_documents(
            all_documents
        )
    )

    all_assets = (
        deduplicate_assets(
            all_assets
        )
    )

    # =====================================================
    # Save
    # =====================================================

    save_jsonl(
        all_documents,
        DOCUMENT_OUTPUT,
    )

    save_jsonl(
        all_assets,
        ASSET_OUTPUT,
    )

    # =====================================================
    # Summary
    # =====================================================

    total_type_counts = Counter(
        document.metadata.get(
            "content_type",
            "unknown",
        )
        for document
        in all_documents
    )

    print(
        "\nFST curation completed."
    )

    print(
        f"Total documents: "
        f"{len(all_documents)}"
    )

    print(
        f"Total image assets: "
        f"{len(all_assets)}"
    )

    print(
        "Content type summary:"
    )

    for (
        content_type,
        count,
    ) in sorted(
        total_type_counts.items()
    ):

        print(
            f"  {content_type}: "
            f"{count}"
        )

    print(
        "\nDocuments saved to:"
    )

    print(
        DOCUMENT_OUTPUT
    )

    print(
        "\nAssets saved to:"
    )

    print(
        ASSET_OUTPUT
    )


if __name__ == "__main__":
    main()