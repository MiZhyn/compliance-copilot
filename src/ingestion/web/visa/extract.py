from __future__ import annotations

import json
import re

from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import (
    BeautifulSoup,
    NavigableString,
    Tag,
)


# =========================================================
# Configuration
# =========================================================

EXTRACTOR_VERSION = (
    "2026-08-08-ica-structured-v2"
)

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[4]
)

RAW_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "web"
    / "visa"
)

HTML_DIR = (
    RAW_DIR
    / "html"
)

MANIFEST_PATH = (
    RAW_DIR
    / "fetch_manifest.json"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "visa"
)

PROCESSED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

REPORT_PATH = (
    PROCESSED_DIR
    / "extraction_report.json"
)


# =========================================================
# Known fallback URLs
# =========================================================

# Used only when an HTML file exists locally but is
# missing from the latest fetch manifest.
#
# Normally the manifest should provide the URL.

FALLBACK_URLS = {
    "visa-free-transit-facility": (
        "https://www.ica.gov.sg/"
        "enter-transit-depart/"
        "entering-singapore/"
        "visa-free-transit-facility"
    ),

    "ica_visa_requirements": (
        "https://www.ica.gov.sg/"
        "enter-transit-depart/"
        "entering-singapore/"
        "visa_requirements"
    ),
}


# =========================================================
# Text utilities
# =========================================================

def clean_text(
    value: str | None,
) -> str:
    """
    Single-line normalization.

    Best for:
    - titles
    - labels
    - country names
    """

    if not value:
        return ""

    value = str(
        value
    )

    value = value.replace(
        "\xa0",
        " ",
    )

    value = re.sub(
        r"[\u200b\u200c\u200d\ufeff]",
        "",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def clean_multiline(
    value: str | None,
) -> str:
    """
    Normalize text while preserving useful:
    - paragraph breaks
    - list boundaries
    - line breaks
    """

    if not value:
        return ""

    value = str(
        value
    )

    value = value.replace(
        "\xa0",
        " ",
    )

    value = re.sub(
        r"[\u200b\u200c\u200d\ufeff]",
        "",
        value,
    )

    # Horizontal spaces only
    value = re.sub(
        r"[ \t]+",
        " ",
        value,
    )

    # Remove spaces around line breaks
    value = re.sub(
        r" *\n *",
        "\n",
        value,
    )

    # Avoid too many blank lines
    value = re.sub(
        r"\n{3,}",
        "\n\n",
        value,
    )

    return value.strip()


def slugify(
    value: str,
) -> str:

    value = clean_text(
        value
    ).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    return value.strip(
        "-"
    )


def remove_footnote_markers(
    value: str,
) -> str:
    """
    Clean title-only footnote references.

    Example:

        Nationals of India and selected [2] Nationals of PRC

    becomes:

        Nationals of India and selected Nationals of PRC

    The actual footnote content is preserved separately.
    """

    value = re.sub(
        r"\s*\[\d+\]\s*",
        " ",
        value,
    )

    return clean_text(
        value
    )


# =========================================================
# HTML -> readable text
# =========================================================

def render_node(
    node: Any,
    base_url: str,
) -> str:
    """
    Recursively convert HTML into readable text.

    Preserves:
    - links
    - paragraphs
    - bullets
    - <br> line breaks
    """

    # -----------------------------------------------------
    # Raw text
    # -----------------------------------------------------

    if isinstance(
        node,
        NavigableString,
    ):

        return str(
            node
        )

    if not isinstance(
        node,
        Tag,
    ):

        return ""

    # -----------------------------------------------------
    # Ignore technical / non-content elements
    # -----------------------------------------------------

    if node.name in {
        "script",
        "style",
        "noscript",
        "template",
        "svg",
    }:

        return ""

    # -----------------------------------------------------
    # Link
    # -----------------------------------------------------

    if node.name == "a":

        label = clean_text(
            node.get_text(
                " ",
                strip=True,
            )
        )

        href = clean_text(
            node.get(
                "href"
            )
        )

        if not label:
            return ""

        # Internal footnote reference
        if (
            not href
            or href.startswith(
                "#"
            )
        ):

            return label

        absolute_url = urljoin(
            base_url,
            href,
        )

        return (
            f"[{label}]"
            f"({absolute_url})"
        )

    # -----------------------------------------------------
    # Explicit line break
    # -----------------------------------------------------

    if node.name == "br":

        return "\n"

    # -----------------------------------------------------
    # List item
    # -----------------------------------------------------

    if node.name == "li":

        inner = "".join(
            render_node(
                child,
                base_url,
            )
            for child
            in node.children
        )

        inner = clean_multiline(
            inner
        )

        if not inner:
            return ""

        lines = inner.split(
            "\n"
        )

        if len(lines) == 1:

            return (
                "\n- "
                f"{lines[0]}"
                "\n"
            )

        formatted = (
            "- "
            + lines[0]
        )

        for line in lines[
            1:
        ]:

            if line:

                formatted += (
                    "\n  "
                    + line
                )

        return (
            "\n"
            + formatted
            + "\n"
        )

    # -----------------------------------------------------
    # Generic element
    # -----------------------------------------------------

    inner = "".join(
        render_node(
            child,
            base_url,
        )
        for child
        in node.children
    )

    if node.name in {
        "p",
        "div",
        "section",
        "article",
        "ul",
        "ol",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }:

        return (
            "\n"
            + inner
            + "\n"
        )

    return inner


def extract_text(
    element: Tag | None,
    base_url: str,
) -> str:

    if element is None:
        return ""

    rendered = render_node(
        element,
        base_url,
    )

    return clean_multiline(
        rendered
    )


def extract_list_items(
    list_element: Tag | None,
    base_url: str,
) -> list[str]:

    if list_element is None:
        return []

    results = []

    for li in list_element.find_all(
        "li",
        recursive=False,
    ):

        text = extract_text(
            li,
            base_url,
        )

        text = re.sub(
            r"^\-\s*",
            "",
            text,
        ).strip()

        if text:

            results.append(
                text
            )

    return results


# =========================================================
# Page utilities
# =========================================================

def get_page_title(
    soup: BeautifulSoup,
) -> str:
    """
    Prefer visible ICA page title.

    Important because country detail pages may have:

        <title>
            ICA | Visa Detail Page
        </title>

    while the useful visible title is:

        India Visa Requirements
    """

    title_element = soup.select_one(
        "h1.my-bread-crumbs-title"
    )

    if title_element:

        title = clean_text(
            title_element.get_text(
                " ",
                strip=True,
            )
        )

        if title:
            return title

    # Fallback generic H1
    h1 = soup.find(
        "h1"
    )

    if h1:

        title = clean_text(
            h1.get_text(
                " ",
                strip=True,
            )
        )

        if title:
            return title

    # Final fallback
    if soup.title:

        title = clean_text(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )

        title = re.sub(
            r"^ICA\s*\|\s*",
            "",
            title,
            flags=re.IGNORECASE,
        )

        return title

    return ""


def detect_page_type(
    soup: BeautifulSoup,
    page_id: str,
) -> str:
    """
    Detect the three ICA page structures.

    Priority:
    1. country detail
    2. visa index
    3. VFTF
    """

    # -----------------------------------------------------
    # Country-specific visa detail
    # -----------------------------------------------------

    if soup.select_one(
        ".visa-detail"
    ):

        return "visa_detail"

    # -----------------------------------------------------
    # Visa requirements index
    # -----------------------------------------------------

    if soup.select_one(
        ".countries-list__links"
    ):

        return "visa_index"

    # -----------------------------------------------------
    # VFTF
    # -----------------------------------------------------

    title = get_page_title(
        soup
    )

    if (
        "visa free transit facility"
        in title.lower()
        or page_id
        == "visa-free-transit-facility"
    ):

        return "vftf"

    return "unknown"


# =========================================================
# ICA Visa Index
# =========================================================

def extract_index_overview(
    soup: BeautifulSoup,
    base_url: str,
) -> str:
    """
    Extract introductory visa guidance appearing before
    the accordion sections.
    """

    article = soup.select_one(
        ".standard-content "
        ".sf_colsIn.article"
    )

    if article is None:
        return ""

    return extract_text(
        article,
        base_url,
    )


def clean_accordion_title(
    title_element: Tag,
) -> str:
    """
    ICA accordion title containers may also contain
    buttons such as:

        Apply Online

    Remove button text before getting semantic title.
    """

    clone = deepcopy(
        title_element
    )

    for anchor in clone.select(
        "a.btn"
    ):

        anchor.decompose()

    return clean_text(
        clone.get_text(
            " ",
            strip=True,
        )
    )


def extract_index_sections(
    soup: BeautifulSoup,
    base_url: str,
) -> tuple[
    list[dict[str, Any]],
    str,
]:
    """
    Extract accordion sections from ICA visa index.

    The country list itself is extracted separately
    as structured data.
    """

    sections = []

    country_list_description = ""

    for wrapper in soup.select(
        ".collapse-wrapper"
    ):

        title_element = wrapper.select_one(
            ".collapse-title"
        )

        content_element = wrapper.select_one(
            ".collapse-content"
        )

        if (
            title_element is None
            or content_element is None
        ):

            continue

        title = clean_accordion_title(
            title_element
        )

        if not title:
            continue

        content_clone = deepcopy(
            content_element
        )

        # -------------------------------------------------
        # Remove structured countries UI from text.
        #
        # Other explanatory content remains:
        # special travel documents + VFTF information.
        # -------------------------------------------------

        countries_list = (
            content_clone.select_one(
                ".countries-list"
            )
        )

        if countries_list:

            countries_list.decompose()

        content = extract_text(
            content_clone,
            base_url,
        )

        if (
            title.lower()
            == (
                "travel documents "
                "by countries and places"
            )
        ):

            country_list_description = (
                content
            )

            continue

        sections.append({
            "title": title,

            "content": (
                content
            ),
        })

    return (
        sections,
        country_list_description,
    )


def extract_countries(
    soup: BeautifulSoup,
    base_url: str,
) -> list[dict[str, str]]:
    """
    Extract structured country/place links.

    This uses the actual ICA component:

        .countries-list__links
    """

    countries = []

    seen_urls = set()

    for anchor in soup.select(
        ".countries-list__links "
        "a[href*='visa-detail-page']"
    ):

        name = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        href = clean_text(
            anchor.get(
                "href"
            )
        )

        if (
            not name
            or not href
        ):

            continue

        url = urljoin(
            base_url,
            href,
        )

        if url in seen_urls:
            continue

        seen_urls.add(
            url
        )

        countries.append({
            "name": name,

            "url": url,
        })

    return countries


def extract_visa_index(
    *,
    soup: BeautifulSoup,
    page_id: str,
    url: str,
) -> dict[str, Any]:

    title = get_page_title(
        soup
    )

    overview = extract_index_overview(
        soup,
        url,
    )

    (
        sections,
        country_list_description,
    ) = extract_index_sections(
        soup,
        url,
    )

    countries = extract_countries(
        soup,
        url,
    )

    return {
        "extractor_version": (
            EXTRACTOR_VERSION
        ),

        "id": page_id,

        "source": "ica",

        "page_type": (
            "visa_index"
        ),

        "title": title,

        "url": url,

        "overview": overview,

        "sections": sections,

        "country_list": {
            "title": (
                "Travel Documents "
                "by Countries and Places"
            ),

            "description": (
                country_list_description
            ),

            "countries": (
                countries
            ),
        },

        "extraction_summary": {
            "section_count": len(
                sections
            ),

            "country_count": len(
                countries
            ),
        },
    }


# =========================================================
# ICA Country Visa Detail
# =========================================================

def country_from_title(
    title: str,
) -> str:
    """
    Example:

        India Visa Requirements

    becomes:

        India
    """

    country = re.sub(
        r"\s+Visa Requirements\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )

    return clean_text(
        country
    )


def extract_section_actions(
    title_container: Tag | None,
    base_url: str,
) -> list[dict[str, str]]:
    """
    Preserve action buttons such as:

        Apply Online
    """

    if title_container is None:
        return []

    actions = []

    for anchor in title_container.select(
        "a.btn[href]"
    ):

        text = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        href = clean_text(
            anchor.get(
                "href"
            )
        )

        if (
            not text
            or not href
        ):

            continue

        actions.append({
            "text": text,

            "url": urljoin(
                base_url,
                href,
            ),
        })

    return actions


def extract_tooltip_notes(
    section: Tag,
    base_url: str,
) -> list[str]:
    """
    Tooltip information is useful policy guidance,
    but structurally it is auxiliary information.

    Preserve it as notes rather than merging it into
    the main section text.
    """

    notes = []

    for tooltip in section.select(
        ".tooltip-content"
    ):

        text = extract_text(
            tooltip,
            base_url,
        )

        if text:

            notes.append(
                text
            )

    return notes


def extract_country_detail_sections(
    visa_detail: Tag,
    base_url: str,
) -> tuple[
    str,
    list[dict[str, Any]],
]:
    """
    Extract:

        introductory visa requirement

        Documents Required
        Procedure
        Fees
        Processing Time
        Collection

    from ICA's .visa-detail component.
    """

    requirement_parts = []

    sections = []

    blocks = visa_detail.find_all(
        "div",
        class_="standard-rich-text",
        recursive=False,
    )

    for block in blocks:

        title_container = (
            block.select_one(
                ".standard-rich-text__title"
            )
        )

        title_element = (
            title_container.find(
                [
                    "h1",
                    "h2",
                    "h3",
                ]
            )
            if title_container
            else None
        )

        # -------------------------------------------------
        # Untitled intro block
        #
        # Example:
        # "You will need a visa to enter Singapore..."
        # -------------------------------------------------

        if title_element is None:

            text = extract_text(
                block,
                base_url,
            )

            if text:

                requirement_parts.append(
                    text
                )

            continue

        section_title = clean_text(
            title_element.get_text(
                " ",
                strip=True,
            )
        )

        if not section_title:
            continue

        # -------------------------------------------------
        # Auxiliary structured information
        # -------------------------------------------------

        notes = extract_tooltip_notes(
            block,
            base_url,
        )

        actions = extract_section_actions(
            title_container,
            base_url,
        )

        # -------------------------------------------------
        # Main body content
        #
        # Remove title container completely so:
        # - title
        # - Apply Online button
        # - tooltip
        #
        # are not repeated inside content.
        # -------------------------------------------------

        clone = deepcopy(
            block
        )

        clone_title = clone.select_one(
            ".standard-rich-text__title"
        )

        if clone_title:

            clone_title.decompose()

        content = extract_text(
            clone,
            base_url,
        )

        sections.append({
            "title": (
                section_title
            ),

            "content": (
                content
            ),

            "notes": (
                notes
            ),

            "actions": (
                actions
            ),
        })

    requirement_text = (
        "\n\n".join(
            requirement_parts
        )
    )

    return (
        requirement_text,
        sections,
    )


def extract_visa_detail(
    *,
    soup: BeautifulSoup,
    page_id: str,
    url: str,
) -> dict[str, Any]:

    title = get_page_title(
        soup
    )

    country = country_from_title(
        title
    )

    visa_detail = soup.select_one(
        ".visa-detail"
    )

    if visa_detail is None:

        raise ValueError(
            "Could not find .visa-detail "
            f"for {page_id}"
        )

    (
        requirement_text,
        sections,
    ) = extract_country_detail_sections(
        visa_detail,
        url,
    )

    return {
        "extractor_version": (
            EXTRACTOR_VERSION
        ),

        "id": page_id,

        "source": "ica",

        "page_type": (
            "visa_detail"
        ),

        "country": country,

        "title": title,

        "url": url,

        "visa_requirement": {
            # These pages originate from ICA's
            # visa-required country/place list.
            #
            # Country-specific exceptions remain
            # inside the content text.
            "required": True,

            "content": (
                requirement_text
            ),
        },

        "sections": (
            sections
        ),

        "extraction_summary": {
            "section_count": len(
                sections
            ),
        },
    }


# =========================================================
# Visa-Free Transit Facility
# =========================================================

def extract_vftf_overview(
    article: Tag,
    base_url: str,
) -> str:
    """
    Extract VFTF overview before detailed eligibility rules.

    Keeps important statements such as:
    - 96-hour VFTF
    - eligibility is assessed by ICA
    - extension is not allowed
    """

    parts = []

    for child in article.children:

        if not isinstance(
            child,
            Tag,
        ):

            continue

        # Detailed group / footnote container begins here
        if child.get(
            "id"
        ) == "ftn1":

            break

        if child.name == "p":

            text = extract_text(
                child,
                base_url,
            )

            if text:

                parts.append(
                    text
                )

    return "\n\n".join(
        parts
    )


def is_vftf_group_heading(
    element: Tag,
) -> bool:
    """
    Detect ICA's visual eligibility headings.

    They are bold paragraphs rather than H2/H3.
    """

    if element.name != "p":
        return False

    if element.find(
        "strong"
    ) is None:

        return False

    text = clean_text(
        element.get_text(
            " ",
            strip=True,
        )
    )

    return (
        text.lower()
        .startswith(
            "nationals of"
        )
    )


def extract_vftf_groups(
    article: Tag,
    base_url: str,
) -> list[dict[str, Any]]:
    """
    Keep different VFTF policy groups separate.

    Current ICA structure includes:

    1. India + selected PRC nationals
    2. CIS + Georgia + Turkmenistan + Ukraine
    """

    groups = []

    headings = [
        element

        for element
        in article.find_all(
            "p"
        )

        if is_vftf_group_heading(
            element
        )
    ]

    for heading in headings:

        title = clean_text(
            heading.get_text(
                " ",
                strip=True,
            )
        )

        # [1] / [2] are references, not semantic title text.
        title = remove_footnote_markers(
            title
        )

        content_parts = []

        requirements = []

        sibling = heading.next_sibling

        while sibling is not None:

            # ---------------------------------------------
            # Ignore whitespace strings
            # ---------------------------------------------

            if isinstance(
                sibling,
                NavigableString,
            ):

                sibling = (
                    sibling.next_sibling
                )

                continue

            if not isinstance(
                sibling,
                Tag,
            ):

                sibling = (
                    sibling.next_sibling
                )

                continue

            # ---------------------------------------------
            # Reached next eligibility group
            # ---------------------------------------------

            if is_vftf_group_heading(
                sibling
            ):

                break

            # ---------------------------------------------
            # Footnote container
            # ---------------------------------------------

            sibling_id = clean_text(
                sibling.get(
                    "id"
                )
            )

            if sibling_id.startswith(
                "ftn"
            ):

                sibling = (
                    sibling.next_sibling
                )

                continue

            # ---------------------------------------------
            # Structured requirement list
            # ---------------------------------------------

            if sibling.name in {
                "ul",
                "ol",
            }:

                requirements.extend(
                    extract_list_items(
                        sibling,
                        base_url,
                    )
                )

            # ---------------------------------------------
            # Supporting paragraph
            # ---------------------------------------------

            elif sibling.name == "p":

                text = extract_text(
                    sibling,
                    base_url,
                )

                if text:

                    content_parts.append(
                        text
                    )

            sibling = (
                sibling.next_sibling
            )

        groups.append({
            "title": title,

            "content": (
                "\n\n".join(
                    content_parts
                )
            ),

            "requirements": (
                requirements
            ),
        })

    return groups


def extract_vftf_footnotes(
    article: Tag,
    base_url: str,
) -> list[dict[str, str]]:
    """
    Extract [1], [2], [3] separately.

    This avoids polluting group titles/content while
    retaining important definitions and exceptions.
    """

    footnotes = []

    for number in [
        "1",
        "2",
        "3",
    ]:

        footnote_id = (
            f"ftn{number}"
        )

        container = article.select_one(
            f"#{footnote_id}"
        )

        if container is None:
            continue

        note_paragraph = None

        # -------------------------------------------------
        # Find paragraph beginning with [n]
        # -------------------------------------------------

        for paragraph in container.find_all(
            "p",
            recursive=False,
        ):

            text = clean_text(
                paragraph.get_text(
                    " ",
                    strip=True,
                )
            )

            if text.startswith(
                f"[{number}]"
            ):

                note_paragraph = (
                    paragraph
                )

                break

        if note_paragraph is None:
            continue

        content_parts = [
            extract_text(
                note_paragraph,
                base_url,
            )
        ]

        # -------------------------------------------------
        # Footnote 3 has its own condition list.
        # -------------------------------------------------

        next_sibling = (
            note_paragraph.next_sibling
        )

        while next_sibling is not None:

            if isinstance(
                next_sibling,
                NavigableString,
            ):

                next_sibling = (
                    next_sibling.next_sibling
                )

                continue

            if not isinstance(
                next_sibling,
                Tag,
            ):

                break

            if next_sibling.name in {
                "ul",
                "ol",
            }:

                items = extract_list_items(
                    next_sibling,
                    base_url,
                )

                if items:

                    content_parts.append(
                        "\n".join(
                            f"- {item}"
                            for item
                            in items
                        )
                    )

            break

        content = "\n\n".join(
            part
            for part
            in content_parts
            if part
        )

        footnotes.append({
            "id": footnote_id,

            "number": number,

            "content": content,
        })

    return footnotes


def extract_vftf(
    *,
    soup: BeautifulSoup,
    page_id: str,
    url: str,
) -> dict[str, Any]:

    title = get_page_title(
        soup
    )

    article = soup.select_one(
        ".standard-content "
        ".sf_colsIn.article"
    )

    if article is None:

        raise ValueError(
            "Could not find VFTF article content."
        )

    overview = extract_vftf_overview(
        article,
        url,
    )

    eligibility_groups = (
        extract_vftf_groups(
            article,
            url,
        )
    )

    footnotes = (
        extract_vftf_footnotes(
            article,
            url,
        )
    )

    return {
        "extractor_version": (
            EXTRACTOR_VERSION
        ),

        "id": page_id,

        "source": "ica",

        "page_type": (
            "vftf"
        ),

        "title": title,

        "url": url,

        "overview": overview,

        "eligibility_groups": (
            eligibility_groups
        ),

        "footnotes": (
            footnotes
        ),

        "extraction_summary": {
            "eligibility_group_count": (
                len(
                    eligibility_groups
                )
            ),

            "footnote_count": (
                len(
                    footnotes
                )
            ),
        },
    }


# =========================================================
# Manifest
# =========================================================

def load_manifest() -> dict[str, Any]:
    """
    Load fetch metadata.

    Preferred source for:
    - page_id
    - URL
    - fetch status
    - raw HTML location
    """

    if not MANIFEST_PATH.exists():

        return {
            "pages": []
        }

    return json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )


def build_source_records() -> list[dict[str, str]]:
    """
    Build all extraction input records.

    Priority:

        fetch_manifest.json
            ↓
        local raw HTML fallback

    The fallback is useful when a previously downloaded
    VFTF HTML file exists but the latest fetch run only
    fetched visa-detail pages.
    """

    manifest = load_manifest()

    records_by_page_id: dict[
        str,
        dict[str, str],
    ] = {}

    # =====================================================
    # 1. Manifest-backed pages
    # =====================================================

    for page in manifest.get(
        "pages",
        [],
    ):

        if page.get(
            "fetch_status"
        ) != "success":

            continue

        page_id = clean_text(
            page.get(
                "page_id"
            )
        )

        if not page_id:
            continue

        html_path_value = clean_text(
            page.get(
                "html_path"
            )
        )

        if html_path_value:

            html_path = (
                PROJECT_ROOT
                / html_path_value
            )

        else:

            html_path = (
                HTML_DIR
                / f"{page_id}.html"
            )

        records_by_page_id[
            page_id
        ] = {
            "page_id": page_id,

            "url": clean_text(
                page.get(
                    "url"
                )
            ),

            "html_path": str(
                html_path
            ),
        }

    # =====================================================
    # 2. Local HTML fallback
    # =====================================================

    if HTML_DIR.exists():

        for html_path in HTML_DIR.glob(
            "*.html"
        ):

            page_id = (
                html_path.stem
            )

            # Already provided by manifest
            if (
                page_id
                in records_by_page_id
            ):

                continue

            records_by_page_id[
                page_id
            ] = {
                "page_id": page_id,

                # Key fix:
                # preserve URL even for fallback pages.
                "url": FALLBACK_URLS.get(
                    page_id,
                    "",
                ),

                "html_path": str(
                    html_path
                ),
            }

    return sorted(
        records_by_page_id.values(),

        key=lambda record: (
            record[
                "page_id"
            ]
        ),
    )


# =========================================================
# Extract one page
# =========================================================

def extract_page(
    record: dict[str, str],
) -> dict[str, Any]:

    page_id = record[
        "page_id"
    ]

    url = record.get(
        "url",
        "",
    )

    html_path = Path(
        record[
            "html_path"
        ]
    )

    if not html_path.exists():

        raise FileNotFoundError(
            f"Missing HTML: "
            f"{html_path}"
        )

    html = html_path.read_text(
        encoding="utf-8"
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    page_type = detect_page_type(
        soup,
        page_id,
    )

    # =====================================================
    # Visa index
    # =====================================================

    if page_type == "visa_index":

        return extract_visa_index(
            soup=soup,

            page_id=page_id,

            url=url,
        )

    # =====================================================
    # Country detail
    # =====================================================

    if page_type == "visa_detail":

        return extract_visa_detail(
            soup=soup,

            page_id=page_id,

            url=url,
        )

    # =====================================================
    # VFTF
    # =====================================================

    if page_type == "vftf":

        return extract_vftf(
            soup=soup,

            page_id=page_id,

            url=url,
        )

    raise ValueError(
        "Unsupported ICA page type: "
        f"{page_id}"
    )


# =========================================================
# Save processed JSON
# =========================================================

def save_processed_page(
    page: dict[str, Any],
) -> Path:

    output_path = (
        PROCESSED_DIR
        / f"{page['id']}.json"
    )

    output_path.write_text(
        json.dumps(
            page,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output_path


# =========================================================
# Main
# =========================================================

def main() -> None:

    records = (
        build_source_records()
    )

    if not records:

        raise FileNotFoundError(
            "No ICA raw HTML files found in: "
            f"{HTML_DIR}"
        )

    report = []

    for record in records:

        page_id = record[
            "page_id"
        ]

        print(
            f"\nExtracting: "
            f"{page_id}"
        )

        try:

            page = extract_page(
                record
            )

            output_path = (
                save_processed_page(
                    page
                )
            )

            report.append({
                "page_id": page_id,

                "page_type": (
                    page[
                        "page_type"
                    ]
                ),

                "status": (
                    "success"
                ),

                "output": str(
                    output_path
                ),

                "summary": (
                    page.get(
                        "extraction_summary",
                        {},
                    )
                ),
            })

            print(
                f"  Type: "
                f"{page['page_type']}"
            )

            print(
                f"  Saved: "
                f"{output_path}"
            )

            print(
                "  Summary: "
                f"{page.get('extraction_summary', {})}"
            )

        except Exception as exc:

            report.append({
                "page_id": (
                    page_id
                ),

                "status": (
                    "failed"
                ),

                "error": str(
                    exc
                ),
            })

            print(
                f"  FAILED: "
                f"{exc}"
            )

    # =====================================================
    # Save extraction report
    # =====================================================

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    successful_count = sum(
        item[
            "status"
        ] == "success"

        for item
        in report
    )

    failed_count = (
        len(
            report
        )
        - successful_count
    )

    print(
        "\nICA extraction completed."
    )

    print(
        f"Successful: "
        f"{successful_count}"
    )

    print(
        f"Failed: "
        f"{failed_count}"
    )

    print(
        f"Processed folder: "
        f"{PROCESSED_DIR}"
    )

    print(
        f"Report: "
        f"{REPORT_PATH}"
    )


if __name__ == "__main__":
    main()