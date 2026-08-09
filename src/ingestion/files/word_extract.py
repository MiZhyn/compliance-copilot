from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

RAW_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "word"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "word"
)

PROCESSED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Helpers
# =========================================================

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+"
)


def clean_text(
    value: str,
    preserve_newlines: bool = False,
) -> str:
    """
    Normalise Word text while preserving useful content.
    """

    if not value:
        return ""

    value = value.replace(
        "\xa0",
        " ",
    )

    if preserve_newlines:

        lines = []

        for line in value.splitlines():

            line = re.sub(
                r"[ \t]+",
                " ",
                line,
            ).strip()

            if line:
                lines.append(
                    line
                )

        return "\n".join(
            lines
        )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


# =========================================================
# Preserve document order
# =========================================================

def iter_block_items(
    document: DocumentType,
):
    """
    Iterate through paragraphs and tables
    in the order they appear in Word.
    """

    for child in (
        document.element.body.iterchildren()
    ):

        if child.tag.endswith(
            "}p"
        ):

            yield Paragraph(
                child,
                document,
            )

        elif child.tag.endswith(
            "}tbl"
        ):

            yield Table(
                child,
                document,
            )


# =========================================================
# Paragraph text
# =========================================================

def extract_full_paragraph_text(
    paragraph: Paragraph,
) -> str:
    """
    Read text directly from XML so hyperlink text
    is also preserved.

    This is more robust than relying only on runs.
    """

    parts = []

    for node in paragraph._p.iter():

        if node.tag == qn(
            "w:t"
        ):

            if node.text:
                parts.append(
                    node.text
                )

        elif node.tag == qn(
            "w:tab"
        ):

            parts.append(
                " "
            )

        elif node.tag == qn(
            "w:br"
        ):

            parts.append(
                "\n"
            )

    return clean_text(
        "".join(parts)
    )


# =========================================================
# Hyperlinks
# =========================================================

def extract_hyperlinks(
    paragraph: Paragraph,
) -> list[dict]:
    """
    Extract Word hyperlink text and target URL.

    Example:

    Customs Appeals Form
        ->
    https://...
    """

    hyperlinks = []

    # -----------------------------------------------------
    # Word hyperlink objects
    # -----------------------------------------------------

    for hyperlink in paragraph._p.iter(
        qn("w:hyperlink")
    ):

        text_parts = []

        for text_node in hyperlink.iter(
            qn("w:t")
        ):

            if text_node.text:

                text_parts.append(
                    text_node.text
                )

        link_text = clean_text(
            "".join(
                text_parts
            )
        )

        relationship_id = hyperlink.get(
            qn("r:id")
        )

        anchor = hyperlink.get(
            qn("w:anchor")
        )

        url = None

        if (
            relationship_id
            and relationship_id
            in paragraph.part.rels
        ):

            url = (
                paragraph.part
                .rels[relationship_id]
                .target_ref
            )

        elif anchor:

            url = (
                f"#{anchor}"
            )

        if (
            link_text
            and url
        ):

            hyperlinks.append({
                "text": link_text,
                "url": url,
            })

    # -----------------------------------------------------
    # Also catch plain-text URLs
    # -----------------------------------------------------

    full_text = (
        extract_full_paragraph_text(
            paragraph
        )
    )

    for match in URL_PATTERN.findall(
        full_text
    ):

        hyperlinks.append({
            "text": match,
            "url": match,
        })

    # -----------------------------------------------------
    # Deduplicate
    # -----------------------------------------------------

    unique_links = []

    seen = set()

    for link in hyperlinks:

        key = (
            link["text"],
            link["url"],
        )

        if key not in seen:

            seen.add(
                key
            )

            unique_links.append(
                link
            )

    return unique_links


# =========================================================
# Formatting
# =========================================================

def extract_formatting(
    paragraph: Paragraph,
) -> dict:
    """
    Extract visual formatting signals.

    These are observations, not semantic decisions.
    """

    text_runs = [
        run
        for run in paragraph.runs
        if clean_text(
            run.text
        )
    ]

    total_characters = sum(
        len(
            clean_text(
                run.text
            )
        )
        for run in text_runs
    )

    bold_characters = sum(
        len(
            clean_text(
                run.text
            )
        )
        for run in text_runs
        if run.bold is True
    )

    bold_ratio = (
        bold_characters
        / total_characters
        if total_characters
        else 0
    )

    font_sizes = [
        run.font.size.pt
        for run in text_runs
        if run.font.size
        is not None
    ]

    max_font_size = (
        max(font_sizes)
        if font_sizes
        else None
    )

    return {
        "bold_ratio": round(
            bold_ratio,
            2,
        ),

        "mostly_bold": (
            bold_ratio >= 0.8
        ),

        "max_font_size_pt": (
            max_font_size
        ),
    }


# =========================================================
# List / bullet detection
# =========================================================

def _read_num_pr(
    num_pr,
    source: str,
) -> dict | None:
    """
    Read Word numbering metadata.
    """

    if num_pr is None:
        return None

    level = 0
    num_id = None

    if (
        num_pr.ilvl
        is not None
        and num_pr.ilvl.val
        is not None
    ):

        level = int(
            num_pr.ilvl.val
        )

    if (
        num_pr.numId
        is not None
        and num_pr.numId.val
        is not None
    ):

        num_id = int(
            num_pr.numId.val
        )

    return {
        "is_list_item": True,
        "level": level,
        "num_id": num_id,
        "detected_from": source,
    }


def extract_list_info(
    paragraph: Paragraph,
) -> dict:
    """
    Detect Word bullet / numbered-list paragraphs.

    We check:
    1. paragraph-level numbering
    2. style-level numbering
    3. list-style name as fallback
    """

    # -----------------------------------------------------
    # Direct paragraph numbering
    # -----------------------------------------------------

    p_pr = paragraph._p.pPr

    if (
        p_pr is not None
        and p_pr.numPr
        is not None
    ):

        result = _read_num_pr(
            p_pr.numPr,
            "paragraph",
        )

        if result:
            return result

    # -----------------------------------------------------
    # Numbering inherited from Word style
    # -----------------------------------------------------

    if paragraph.style:

        style_p_pr = (
            paragraph.style
            .element
            .pPr
        )

        if (
            style_p_pr
            is not None
            and style_p_pr.numPr
            is not None
        ):

            result = _read_num_pr(
                style_p_pr.numPr,
                "style",
            )

            if result:
                return result

        style_name = (
            paragraph.style.name
            or ""
        )

        if (
            "list"
            in style_name.lower()
        ):

            return {
                "is_list_item": True,
                "level": 0,
                "num_id": None,
                "detected_from": "style_name",
            }

    return {
        "is_list_item": False,
        "level": None,
        "num_id": None,
        "detected_from": None,
    }


# =========================================================
# Paragraph extraction
# =========================================================

def extract_paragraph(
    paragraph: Paragraph,
) -> dict | None:

    text = (
        extract_full_paragraph_text(
            paragraph
        )
    )

    if not text:
        return None

    style = (
        paragraph.style.name
        if paragraph.style
        else None
    )

    return {
        "type": "paragraph",

        "style": style,

        "text": text,

        "formatting": (
            extract_formatting(
                paragraph
            )
        ),

        "list": (
            extract_list_info(
                paragraph
            )
        ),

        "hyperlinks": (
            extract_hyperlinks(
                paragraph
            )
        ),
    }


# =========================================================
# Table extraction
# =========================================================

def extract_table(
    table: Table,
) -> dict:

    rows = []

    hyperlinks = []

    for row in table.rows:

        cells = []

        for cell in row.cells:

            cell_text = clean_text(
                cell.text,
                preserve_newlines=True,
            )

            cells.append(
                cell_text
            )

            # ---------------------------------------------
            # Preserve hyperlinks inside table cells too
            # ---------------------------------------------

            for paragraph in cell.paragraphs:

                hyperlinks.extend(
                    extract_hyperlinks(
                        paragraph
                    )
                )

        rows.append(
            cells
        )

    # -----------------------------------------------------
    # Deduplicate table links
    # -----------------------------------------------------

    unique_links = []

    seen = set()

    for link in hyperlinks:

        key = (
            link["text"],
            link["url"],
        )

        if key not in seen:

            seen.add(
                key
            )

            unique_links.append(
                link
            )

    return {
        "type": "table",
        "rows": rows,
        "hyperlinks": unique_links,
    }


# =========================================================
# Extract Word document
# =========================================================

def extract_word(
    file_path: Path,
) -> dict:

    document = Document(
        file_path
    )

    blocks = []

    for block in iter_block_items(
        document
    ):

        if isinstance(
            block,
            Paragraph,
        ):

            result = (
                extract_paragraph(
                    block
                )
            )

            if result:

                blocks.append(
                    result
                )

        elif isinstance(
            block,
            Table,
        ):

            blocks.append(
                extract_table(
                    block
                )
            )

    return {
        "source_file": (
            file_path.name
        ),

        "source_type": "word",

        "blocks": blocks,
    }


# =========================================================
# Save processed JSON
# =========================================================

def save_processed(
    data: dict,
    source_path: Path,
) -> Path:

    output_path = (
        PROCESSED_DIR
        / f"{source_path.stem}.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return output_path


# =========================================================
# Main
# =========================================================

def main() -> None:

    # Ignore Microsoft Word temporary lock files:
    #
    # ~$avel Rules and Penalties.docx

    files = sorted([
        file_path
        for file_path
        in RAW_DIR.glob("*.docx")
        if not file_path.name.startswith(
            "~$"
        )
    ])

    if not files:

        raise FileNotFoundError(
            f"No DOCX files found in "
            f"{RAW_DIR}"
        )

    print(
        f"Word files found: "
        f"{len(files)}"
    )

    for file_path in files:

        print(
            f"\nProcessing: "
            f"{file_path.name}"
        )

        data = extract_word(
            file_path
        )

        output_path = (
            save_processed(
                data,
                file_path,
            )
        )

        print(
            f"Blocks extracted: "
            f"{len(data['blocks'])}"
        )

        print(
            f"Saved to: "
            f"{output_path}"
        )


if __name__ == "__main__":
    main()