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
    / "pdf"
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
    / "customs_pdf_documents.jsonl"
)


# =========================================================
# Document structure
# =========================================================

DOCUMENT_TITLE = (
    "Controlled and Prohibited Goods"
)


SECTION_TITLES = {
    "01": "Identify Your Goods",
    "02": "Controlled Goods",
    "03": "Prohibited Goods",
    "04": (
        "United Nations Security Council Sanctions"
    ),
    "05": "Obtain Permit",
    "06": "Clearance of Goods",
    "07": "Common Questions from AskGov",
}


SECTION_COLUMNS = {
    "01": "left",
    "02": "right",
    "03": "left",
    "04": "right",
    "05": "left",
    "06": "right",
    "07": "left",
}


# =========================================================
# Text fixes
#
# These are PDF text-layer artefacts observed
# in this specific infographic.
# =========================================================

TEXT_FIXES = {
    "Declarations are checke d":
        "Declarations are checked",

    "Delay s":
        "Delays",
}


# =========================================================
# Known wrapped fragments
#
# PDF visually shows one phrase, but the text layer
# sometimes splits it into multiple lines.
#
# We reconstruct those phrases here.
# =========================================================

PHRASE_MERGES = [
    # -----------------------------------------------------
    # Section 02
    # -----------------------------------------------------

    (
        (
            "Allowed to Import with",
            "Approval",
        ),
        "Allowed to Import with Approval",
    ),

    (
        (
            "Controlled goods are allowed, but only with approval",
            "from the relevant Competent Authority (CA).",
        ),
        (
            "Controlled goods are allowed, but only with "
            "approval from the relevant Competent Authority (CA)."
        ),
    ),

    (
        (
            "Medicines and",
            "health products",
        ),
        "Medicines and health products",
    ),

    (
        (
            "Plants and",
            "animals",
        ),
        "Plants and animals",
    ),

    (
        (
            "Telecommunications",
            "equipment",
        ),
        "Telecommunications equipment",
    ),

    (
        (
            "Weapons and",
            "replicas",
        ),
        "Weapons and replicas",
    ),

    # -----------------------------------------------------
    # Section 03
    # -----------------------------------------------------

    (
        (
            "Counterfeit",
            "goods",
        ),
        "Counterfeit goods",
    ),

    (
        (
            "Obscene",
            "publications",
        ),
        "Obscene publications",
    ),

    (
        (
            "Certain weapons",
            "and explosives",
        ),
        "Certain weapons and explosives",
    ),

    (
        (
            "Endangered",
            "wildlife products",
        ),
        "Endangered wildlife products",
    ),

    (
        (
            "Items banned under",
            "Singapore Law",
        ),
        "Items banned under Singapore Law",
    ),

    # -----------------------------------------------------
    # Section 04
    # -----------------------------------------------------

    (
        (
            "Some goods, persons, or countries are subject to",
            "United Nations Security Council (UNSC) Sanctions.",
        ),
        (
            "Some goods, persons, or countries are subject to "
            "United Nations Security Council (UNSC) Sanctions."
        ),
    ),

    (
        (
            "These restrictions may apply even if goods are",
            "otherwise allowed.",
        ),
        (
            "These restrictions may apply even if goods "
            "are otherwise allowed."
        ),
    ),

    # -----------------------------------------------------
    # Section 06
    # -----------------------------------------------------

    (
        (
            "When goods",
            "arrive:",
        ),
        "When goods arrive:",
    ),

    (
        (
            "Permits and approvals are",
            "verified",
        ),
        "Permits and approvals are verified",
    ),

    (
        (
            "Consequences",
            "of non-",
            "compliance:",
        ),
        "Consequences of non-compliance:",
    ),

    (
        (
            "Penalties or enforcement",
            "action",
        ),
        "Penalties or enforcement action",
    ),

    # -----------------------------------------------------
    # FAQ
    # -----------------------------------------------------

    (
        (
            "How do I know if my goods are controlled or",
            "prohibited?",
        ),
        (
            "How do I know if my goods are "
            "controlled or prohibited?"
        ),
    ),

    (
        (
            "Self-check using the HS/CA Product Code",
            "Checker.",
        ),
        (
            "Self-check using the HS/CA "
            "Product Code Checker."
        ),
    ),

    (
        (
            "No. Valid permits (including CA’s approval) must be",
            "obtained prior to importation.",
        ),
        (
            "No. Valid permits (including CA’s approval) "
            "must be obtained prior to importation."
        ),
    ),

    (
        (
            "Goods may be seized and enforcement action",
            "may be taken.",
        ),
        (
            "Goods may be seized and enforcement "
            "action may be taken."
        ),
    ),
]


# =========================================================
# Section header fragments to remove from content
# =========================================================

HEADER_FRAGMENTS = {
    "01": {
        "01.",
        "Identify Your Goods",
    },

    "02": {
        "02.",
        "Controlled Goods",
    },

    "03": {
        "03.",
        "Prohibited Goods",
    },

    "04": {
        "04.",
        "United Nations",
        "Security Council",
        "Sanctions",
    },

    "05": {
        "05.",
        "Obtain Permit",
    },

    "06": {
        "06.",
        "Clearance of",
        "Goods",
    },

    "07": {
        "07.",
        "Common Questions",
        "from AskGov",
    },
}


# =========================================================
# Known list items
#
# Used only for presentation / semantic reconstruction.
# =========================================================

LIST_ITEMS = {
    "01": {
        "What the goods are",
        "How they are used",
        "Where they come from",
        "Who they are for",
    },

    "02": {
        "Medicines and health products",
        "Food items",
        "Plants and animals",
        "Drones",
        "Telecommunications equipment",
        "Weapons and replicas",
    },

    "03": {
        "Counterfeit goods",
        "Obscene publications",
        "Certain weapons and explosives",
        "Endangered wildlife products",
        "Items banned under Singapore Law",
    },

    "04": {
        "Specific goods",
        "Named individuals or entities",
        "Certain countries or regions",
    },

    "05": {
        "Obtain relevant CA’s approval",
        "Prepare required trade documents",
        "Obtain import permit",
    },

    "06": {
        "Declarations are checked",
        "Permits and approvals are verified",
        "Goods may be inspected",
        "Delays",
        "Seizure of goods",
        "Penalties or enforcement action",
    },
}


# =========================================================
# Text helpers
# =========================================================

def clean_text(
    text: str,
) -> str:

    if not text:
        return ""

    text = text.replace(
        "\xa0",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = text.strip()

    return TEXT_FIXES.get(
        text,
        text,
    )


def normalise_key(
    text: str,
) -> str:

    return (
        clean_text(text)
        .casefold()
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
# Geometry helpers
# =========================================================

def get_center(
    line: dict,
) -> tuple[float, float]:

    (
        x0,
        y0,
        x1,
        y1,
    ) = line[
        "bbox_normalized"
    ]

    return (
        (x0 + x1) / 2,
        (y0 + y1) / 2,
    )


def get_y_start(
    line: dict,
) -> float:

    return line[
        "bbox_normalized"
    ][1]


# =========================================================
# Find 01–07 anchors
# =========================================================

def find_section_anchors(
    lines: list[dict],
) -> dict[str, dict]:

    anchors = {}

    pattern = re.compile(
        r"^(0[1-7])\.$"
    )

    for line in lines:

        text = clean_text(
            line.get(
                "text",
                "",
            )
        )

        match = pattern.match(
            text
        )

        if not match:
            continue

        section_number = (
            match.group(1)
        )

        anchors[
            section_number
        ] = line

    missing = (
        set(
            SECTION_TITLES
        )
        - set(
            anchors
        )
    )

    if missing:

        raise ValueError(
            "Missing PDF section anchors: "
            f"{sorted(missing)}"
        )

    return anchors


# =========================================================
# Build section regions dynamically
#
# Important:
#
# We do NOT hard-code absolute pixel values.
#
# 01 / 03 / 05 / 07 form the left column.
# 02 / 04 / 06 form the right column.
#
# The next anchor in the same column tells us
# where the previous section ends.
# =========================================================

def build_section_regions(
    anchors: dict[str, dict],
) -> dict[str, dict]:

    columns = {
        "left": [
            "01",
            "03",
            "05",
            "07",
        ],

        "right": [
            "02",
            "04",
            "06",
        ],
    }

    regions = {}

    for (
        column_name,
        section_numbers,
    ) in columns.items():

        for index, section_number in enumerate(
            section_numbers
        ):

            anchor = (
                anchors[
                    section_number
                ]
            )

            anchor_y = (
                get_y_start(
                    anchor
                )
            )

            # ---------------------------------------------
            # Slight margin above the numeric anchor
            # because the visual title can begin above it.
            # ---------------------------------------------

            y_start = max(
                0,
                anchor_y - 0.025,
            )

            # ---------------------------------------------
            # End at next section in same column
            # ---------------------------------------------

            if (
                index + 1
                < len(
                    section_numbers
                )
            ):

                next_section = (
                    section_numbers[
                        index + 1
                    ]
                )

                next_anchor_y = (
                    get_y_start(
                        anchors[
                            next_section
                        ]
                    )
                )

                y_end = (
                    next_anchor_y
                    - 0.01
                )

            else:

                # Leave footer outside section content.
                y_end = 0.95

            regions[
                section_number
            ] = {
                "column": (
                    column_name
                ),
                "y_start": (
                    y_start
                ),
                "y_end": (
                    y_end
                ),
            }

    return regions


# =========================================================
# Assign each extracted line to a semantic region
# =========================================================

def assign_lines_to_sections(
    lines: list[dict],
    regions: dict[str, dict],
) -> dict[str, list[dict]]:

    assigned = {
        section_number: []
        for section_number
        in SECTION_TITLES
    }

    for line in lines:

        (
            x_center,
            y_center,
        ) = get_center(
            line
        )

        # ---------------------------------------------
        # Left / right column
        # ---------------------------------------------

        line_column = (
            "left"
            if x_center < 0.50
            else "right"
        )

        for (
            section_number,
            region,
        ) in regions.items():

            if (
                line_column
                != region["column"]
            ):
                continue

            if (
                region["y_start"]
                <= y_center
                < region["y_end"]
            ):

                assigned[
                    section_number
                ].append(
                    line
                )

                break

    # ---------------------------------------------
    # Visual ordering inside each section
    # ---------------------------------------------

    for section_number in assigned:

        assigned[
            section_number
        ].sort(
            key=lambda item: (
                item[
                    "bbox_normalized"
                ][1],
                item[
                    "bbox_normalized"
                ][0],
            )
        )

    return assigned


# =========================================================
# Apply text fixes
# =========================================================

def normalise_section_lines(
    lines: list[dict],
) -> list[dict]:

    output = []

    for line in lines:

        item = dict(
            line
        )

        item[
            "text"
        ] = clean_text(
            item.get(
                "text",
                "",
            )
        )

        if item[
            "text"
        ]:

            output.append(
                item
            )

    return output


# =========================================================
# Merge known broken PDF phrases
# =========================================================

def merge_phrase(
    lines: list[dict],
    fragments: tuple[str, ...],
    merged_text: str,
) -> list[dict]:

    fragment_keys = [
        normalise_key(
            item
        )
        for item in fragments
    ]

    matches = []

    for fragment_key in fragment_keys:

        found_index = None

        for index, line in enumerate(
            lines
        ):

            if index in matches:
                continue

            if (
                normalise_key(
                    line["text"]
                )
                == fragment_key
            ):

                found_index = index
                break

        if found_index is None:

            # Not found:
            # leave the source untouched.
            return lines

        matches.append(
            found_index
        )

    selected = [
        lines[index]
        for index
        in matches
    ]

    # -----------------------------------------------------
    # Preserve approximate position
    # -----------------------------------------------------

    first = dict(
        min(
            selected,
            key=lambda item: (
                item[
                    "bbox_normalized"
                ][1],
                item[
                    "bbox_normalized"
                ][0],
            ),
        )
    )

    first[
        "text"
    ] = merged_text

    # -----------------------------------------------------
    # Preserve URLs from all merged fragments
    # -----------------------------------------------------

    urls = []

    for item in selected:

        urls.extend(
            item.get(
                "links",
                [],
            )
        )

    first[
        "links"
    ] = list(
        dict.fromkeys(
            urls
        )
    )

    new_lines = []

    insert_index = min(
        matches
    )

    for index, line in enumerate(
        lines
    ):

        if index == insert_index:

            new_lines.append(
                first
            )

        if index not in matches:

            new_lines.append(
                line
            )

    return new_lines


def merge_known_phrases(
    lines: list[dict],
) -> list[dict]:

    output = list(
        lines
    )

    for (
        fragments,
        merged_text,
    ) in PHRASE_MERGES:

        output = merge_phrase(
            output,
            fragments,
            merged_text,
        )

    output.sort(
        key=lambda item: (
            item[
                "bbox_normalized"
            ][1],
            item[
                "bbox_normalized"
            ][0],
        )
    )

    return output


# =========================================================
# Remove section-number and heading fragments
# =========================================================

def remove_header_fragments(
    section_number: str,
    lines: list[dict],
) -> list[dict]:

    ignored = {
        normalise_key(
            text
        )
        for text
        in HEADER_FRAGMENTS[
            section_number
        ]
    }

    return [
        line
        for line in lines
        if (
            normalise_key(
                line["text"]
            )
            not in ignored
        )
    ]


# =========================================================
# Extract links
# =========================================================

def extract_section_links(
    lines: list[dict],
) -> list[dict]:

    links = []

    seen = set()

    for line in lines:

        text = (
            line[
                "text"
            ]
        )

        for url in line.get(
            "links",
            [],
        ):

            key = (
                text,
                url,
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            links.append({
                "text": text,
                "url": url,
            })

    return links


# =========================================================
# Normal section formatting
# =========================================================

def format_standard_section(
    section_number: str,
    lines: list[dict],
) -> str:

    list_items = {
        normalise_key(
            item
        )
        for item
        in LIST_ITEMS.get(
            section_number,
            set(),
        )
    }

    rendered = []

    for line in lines:

        text = (
            line["text"]
        )

        # -------------------------------------------------
        # Existing PDF bullet
        # -------------------------------------------------

        if text.startswith(
            "•"
        ):

            text = (
                text
                .lstrip("•")
                .strip()
            )

            rendered.append(
                f"- {text}"
            )

            continue

        # -------------------------------------------------
        # Reconstructed semantic list
        # -------------------------------------------------

        if (
            normalise_key(
                text
            )
            in list_items
        ):

            rendered.append(
                f"- {text}"
            )

        else:

            rendered.append(
                text
            )

    return "\n".join(
        rendered
    ).strip()


# =========================================================
# FAQ formatting
# =========================================================

def format_faq_section(
    lines: list[dict],
) -> str:
    """
    After wrapped-line reconstruction, FAQ structure is:

        Q1:
        question
        answer

        Q2:
        question
        answer
        ...

    Any trailing source link is preserved afterwards.
    """

    texts = [
        line["text"]
        for line
        in lines
    ]

    output = []

    index = 0

    while index < len(
        texts
    ):

        text = (
            texts[index]
        )

        if re.match(
            r"^Q[1-4]:$",
            text,
        ):

            question_number = (
                text
                .replace(
                    ":",
                    "",
                )
            )

            question = (
                texts[index + 1]
                if (
                    index + 1
                    < len(texts)
                )
                else ""
            )

            answer = (
                texts[index + 2]
                if (
                    index + 2
                    < len(texts)
                )
                else ""
            )

            output.append(
                f"{question_number}: "
                f"{question}"
            )

            output.append(
                f"A{question_number[1:]}: "
                f"{answer}"
            )

            output.append(
                ""
            )

            index += 3

            continue

        output.append(
            text
        )

        index += 1

    return "\n".join(
        output
    ).strip()


# =========================================================
# Build CanonicalDocument
# =========================================================

def build_document(
    section_number: str,
    lines: list[dict],
    source_file: str,
    page_number: int,
) -> CanonicalDocument:

    title = (
        SECTION_TITLES[
            section_number
        ]
    )

    links = (
        extract_section_links(
            lines
        )
    )

    # -----------------------------------------------------
    # Remove visual heading after collecting links
    # -----------------------------------------------------

    content_lines = (
        remove_header_fragments(
            section_number,
            lines,
        )
    )

    # -----------------------------------------------------
    # Render
    # -----------------------------------------------------

    if section_number == "07":

        content = (
            format_faq_section(
                content_lines
            )
        )

    else:

        content = (
            format_standard_section(
                section_number,
                content_lines,
            )
        )

    return CanonicalDocument(
        doc_id=(
            f"customs-pdf-"
            f"{section_number}-"
            f"{make_slug(title)}"
        ),

        source=(
            "Singapore Customs"
        ),

        source_type=(
            "pdf"
        ),

        title=title,

        heading_path=(
            f"{DOCUMENT_TITLE} "
            f"> {section_number} "
            f"{title}"
        ),

        content=content,

        url=None,

        page=page_number,

        metadata={
            "source_file": (
                source_file
            ),

            "document_title": (
                DOCUMENT_TITLE
            ),

            "section_number": (
                section_number
            ),

            "layout_column": (
                SECTION_COLUMNS[
                    section_number
                ]
            ),

            # Same topic as Word documents
            # so multi-source retrieval can combine them.
            "topic": (
                "controlled_prohibited_goods"
            ),

            "content_role": (
                "examples_and_process"
            ),

            "links": (
                links
            ),
        },
    )


# =========================================================
# Curate one processed PDF
# =========================================================

def curate_pdf(
    data: dict,
) -> list[CanonicalDocument]:

    if not data.get(
        "pages"
    ):

        return []

    documents = []

    for page in data[
        "pages"
    ]:

        lines = (
            page.get(
                "lines",
                [],
            )
        )

        # -------------------------------------------------
        # Step 1:
        # Find physical section anchors
        # -------------------------------------------------

        anchors = (
            find_section_anchors(
                lines
            )
        )

        # -------------------------------------------------
        # Step 2:
        # Derive semantic layout regions
        # -------------------------------------------------

        regions = (
            build_section_regions(
                anchors
            )
        )

        # -------------------------------------------------
        # Step 3:
        # Assign lines using x/y position
        # -------------------------------------------------

        section_lines = (
            assign_lines_to_sections(
                lines,
                regions,
            )
        )

        # -------------------------------------------------
        # Step 4:
        # Reconstruct text within each region
        # -------------------------------------------------

        for section_number in sorted(
            SECTION_TITLES
        ):

            lines_for_section = (
                normalise_section_lines(
                    section_lines[
                        section_number
                    ]
                )
            )

            lines_for_section = (
                merge_known_phrases(
                    lines_for_section
                )
            )

            if not lines_for_section:

                continue

            document = (
                build_document(
                    section_number=(
                        section_number
                    ),

                    lines=(
                        lines_for_section
                    ),

                    source_file=(
                        data[
                            "source_file"
                        ]
                    ),

                    page_number=(
                        page[
                            "page_number"
                        ]
                    ),
                )
            )

            documents.append(
                document
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
            "No processed PDF JSON "
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
            curate_pdf(
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