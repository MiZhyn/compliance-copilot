from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import fitz


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
    / "pdf"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "pdf"
)

RENDER_DIR = (
    PROCESSED_DIR
    / "renders"
)

PROCESSED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RENDER_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Text cleaning
# =========================================================

def clean_text(
    text: str,
) -> str:
    """
    Light text normalisation only.

    Extraction should preserve source meaning.
    Semantic cleaning happens later in curation.
    """

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

    return text.strip()


# =========================================================
# Bounding box helpers
# =========================================================

def bbox_to_list(
    bbox,
) -> list[float]:

    return [
        round(
            float(value),
            2,
        )
        for value in bbox
    ]


def normalise_bbox(
    bbox,
    page_width: float,
    page_height: float,
) -> list[float]:
    """
    Convert PDF coordinates into 0–1 values.

    Useful later when reconstructing infographic regions.
    """

    x0, y0, x1, y1 = bbox

    return [
        round(
            x0 / page_width,
            4,
        ),
        round(
            y0 / page_height,
            4,
        ),
        round(
            x1 / page_width,
            4,
        ),
        round(
            y1 / page_height,
            4,
        ),
    ]


# =========================================================
# Hyperlinks
# =========================================================

def extract_links(
    page: fitz.Page,
) -> list[dict]:
    """
    Extract external hyperlinks together with
    their position on the PDF page.
    """

    links = []

    for link in page.get_links():

        uri = link.get(
            "uri"
        )

        link_rect = link.get(
            "from"
        )

        if (
            not uri
            or link_rect is None
        ):
            continue

        links.append({
            "url": uri,

            "bbox": (
                bbox_to_list(
                    link_rect
                )
            ),
        })

    return links


# =========================================================
# Associate links with lines
# =========================================================

def find_links_for_bbox(
    bbox,
    links: list[dict],
) -> list[str]:
    """
    Attach a hyperlink URL to text lines that
    spatially overlap the hyperlink rectangle.
    """

    line_rect = fitz.Rect(
        bbox
    )

    matched_urls = []

    for link in links:

        link_rect = fitz.Rect(
            link["bbox"]
        )

        if line_rect.intersects(
            link_rect
        ):

            matched_urls.append(
                link["url"]
            )

    return list(
        dict.fromkeys(
            matched_urls
        )
    )


# =========================================================
# Extract text lines with coordinates
# =========================================================

def extract_lines(
    page: fitz.Page,
    page_width: float,
    page_height: float,
    links: list[dict],
) -> list[dict]:
    """
    PyMuPDF's normal plain-text order can be unreliable
    for infographic PDFs.

    Therefore we extract individual words together
    with their coordinates, then reconstruct visual lines.

    get_text("words") returns:

    x0, y0, x1, y1,
    word,
    block_no,
    line_no,
    word_no
    """

    words = page.get_text(
        "words",
        sort=False,
    )

    grouped_words = defaultdict(
        list
    )

    # -----------------------------------------------------
    # Group words using PDF block + line identifiers
    # -----------------------------------------------------

    for word in words:

        (
            x0,
            y0,
            x1,
            y1,
            text,
            block_no,
            line_no,
            word_no,
        ) = word

        grouped_words[
            (
                block_no,
                line_no,
            )
        ].append({
            "text": text,
            "bbox": (
                x0,
                y0,
                x1,
                y1,
            ),
            "word_no": (
                word_no
            ),
        })

    lines = []

    # -----------------------------------------------------
    # Reconstruct each visual line
    # -----------------------------------------------------

    for (
        block_no,
        line_no,
    ), line_words in grouped_words.items():

        # Word order within the line
        line_words = sorted(
            line_words,
            key=lambda item: (
                item[
                    "word_no"
                ]
            ),
        )

        text = clean_text(
            " ".join(
                item["text"]
                for item
                in line_words
            )
        )

        if not text:
            continue

        x0 = min(
            item["bbox"][0]
            for item
            in line_words
        )

        y0 = min(
            item["bbox"][1]
            for item
            in line_words
        )

        x1 = max(
            item["bbox"][2]
            for item
            in line_words
        )

        y1 = max(
            item["bbox"][3]
            for item
            in line_words
        )

        bbox = (
            x0,
            y0,
            x1,
            y1,
        )

        line_links = (
            find_links_for_bbox(
                bbox,
                links,
            )
        )

        lines.append({
            "text": text,

            "block_no": (
                int(
                    block_no
                )
            ),

            "line_no": (
                int(
                    line_no
                )
            ),

            "bbox": (
                bbox_to_list(
                    bbox
                )
            ),

            "bbox_normalized": (
                normalise_bbox(
                    bbox,
                    page_width,
                    page_height,
                )
            ),

            "links": (
                line_links
            ),
        })

    # -----------------------------------------------------
    # Only for easier inspection.
    #
    # This is VISUAL order, not semantic reading order.
    # The curator will reconstruct the infographic layout.
    # -----------------------------------------------------

    lines.sort(
        key=lambda item: (
            item["bbox"][1],
            item["bbox"][0],
        )
    )

    return lines


# =========================================================
# Image metadata
# =========================================================

def extract_image_info(
    page: fitz.Page,
    page_width: float,
    page_height: float,
) -> list[dict]:
    """
    Preserve image positions.

    We are not interpreting the icons yet.
    This only records where images exist.
    """

    images = []

    try:

        image_info = (
            page.get_image_info(
                xrefs=True
            )
        )

    except Exception:

        return []

    for image in image_info:

        bbox = image.get(
            "bbox"
        )

        if not bbox:
            continue

        images.append({
            "xref": (
                image.get(
                    "xref"
                )
            ),

            "width": (
                image.get(
                    "width"
                )
            ),

            "height": (
                image.get(
                    "height"
                )
            ),

            "bbox": (
                bbox_to_list(
                    bbox
                )
            ),

            "bbox_normalized": (
                normalise_bbox(
                    bbox,
                    page_width,
                    page_height,
                )
            ),
        })

    return images


# =========================================================
# Render page for visual validation
# =========================================================

def render_page(
    page: fitz.Page,
    source_path: Path,
    page_number: int,
) -> Path:
    """
    Save a PNG representation of the page.

    This is useful because infographic PDFs must often
    be visually checked during curation.
    """

    output_path = (
        RENDER_DIR
        / (
            f"{source_path.stem}"
            f"_page_{page_number}.png"
        )
    )

    # 1.2x is enough for this demo.
    matrix = fitz.Matrix(
        1.2,
        1.2,
    )

    pixmap = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    pixmap.save(
        output_path
    )

    return output_path


# =========================================================
# Extract one page
# =========================================================

def extract_page(
    page: fitz.Page,
    source_path: Path,
    page_number: int,
) -> dict:

    page_width = float(
        page.rect.width
    )

    page_height = float(
        page.rect.height
    )

    # -----------------------------------------------------
    # Hyperlinks first because text lines can reference them
    # -----------------------------------------------------

    links = extract_links(
        page
    )

    # -----------------------------------------------------
    # Text with layout coordinates
    # -----------------------------------------------------

    lines = extract_lines(
        page=page,
        page_width=page_width,
        page_height=page_height,
        links=links,
    )

    # -----------------------------------------------------
    # Image positions
    # -----------------------------------------------------

    images = extract_image_info(
        page=page,
        page_width=page_width,
        page_height=page_height,
    )

    # -----------------------------------------------------
    # Render
    # -----------------------------------------------------

    render_path = render_page(
        page=page,
        source_path=source_path,
        page_number=page_number,
    )

    return {
        "page_number": (
            page_number
        ),

        "width": round(
            page_width,
            2,
        ),

        "height": round(
            page_height,
            2,
        ),

        "line_count": (
            len(lines)
        ),

        "lines": (
            lines
        ),

        "links": (
            links
        ),

        "image_count": (
            len(images)
        ),

        "images": (
            images
        ),

        "render_file": (
            render_path.name
        ),
    }


# =========================================================
# Extract whole PDF
# =========================================================

def extract_pdf(
    file_path: Path,
) -> dict:

    document = fitz.open(
        file_path
    )

    try:

        pages = []

        for page_index in range(
            len(document)
        ):

            page = document[
                page_index
            ]

            page_number = (
                page_index + 1
            )

            pages.append(
                extract_page(
                    page=page,
                    source_path=file_path,
                    page_number=page_number,
                )
            )

        return {
            "source_file": (
                file_path.name
            ),

            "source_type": "pdf",

            "page_count": (
                len(document)
            ),

            "pages": (
                pages
            ),
        }

    finally:

        document.close()


# =========================================================
# Save JSON
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

    pdf_files = sorted([
        file_path
        for file_path
        in RAW_DIR.glob("*.pdf")
        if not file_path.name.startswith(
            "~$"
        )
    ])

    if not pdf_files:

        raise FileNotFoundError(
            f"No PDF files found in "
            f"{RAW_DIR}"
        )

    print(
        f"PDF files found: "
        f"{len(pdf_files)}"
    )

    for file_path in pdf_files:

        print(
            f"\nProcessing: "
            f"{file_path.name}"
        )

        data = extract_pdf(
            file_path
        )

        output_path = save_processed(
            data=data,
            source_path=file_path,
        )

        print(
            f"Pages extracted: "
            f"{data['page_count']}"
        )

        total_lines = sum(
            page["line_count"]
            for page
            in data["pages"]
        )

        total_links = sum(
            len(
                page["links"]
            )
            for page
            in data["pages"]
        )

        print(
            f"Text lines extracted: "
            f"{total_lines}"
        )

        print(
            f"Hyperlinks extracted: "
            f"{total_links}"
        )

        print(
            f"Saved to: "
            f"{output_path}"
        )


if __name__ == "__main__":
    main()