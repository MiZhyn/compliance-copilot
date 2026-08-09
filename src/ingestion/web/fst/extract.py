import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

from .config import PAGES


# =========================================================
# Configuration
# =========================================================

EXTRACTOR_VERSION = (
    "2026-08-08-fst-structured-components-v7"
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]

RAW_WEB_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "web"
    / "fst"
)

PROCESSED_WEB_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "fst"
)

PROCESSED_WEB_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Basic text utilities
# =========================================================

def clean_text(
    text: str | None,
) -> str:
    """
    Basic whitespace normalization while preserving
    meaningful paragraph breaks.
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


def normalize_alt_text(
    text: str | None,
) -> str:
    """
    Preserve alt text as image metadata.

    IMPORTANT:
    alt is NOT assumed to be the authoritative
    business title.
    """

    return clean_text(
        text
    )


def extract_text_with_links(
    element: Tag,
    base_url: str,
) -> str:
    """
    Extract readable text while preserving hyperlinks
    in Markdown format.

    Example:

        ICA

    becomes:

        [ICA](https://...)
    """

    parts = []

    def walk(
        node: Any,
    ) -> None:

        if isinstance(
            node,
            NavigableString,
        ):

            value = str(
                node
            )

            if value.strip():
                parts.append(
                    value
                )

            return

        if not isinstance(
            node,
            Tag,
        ):
            return

        if node.name in {
            "script",
            "style",
            "noscript",
            "sly",
            "template",
        }:
            return

        # -----------------------------------------
        # Hyperlink
        # -----------------------------------------

        if node.name == "a":

            label = clean_text(
                node.get_text(
                    " ",
                    strip=True,
                )
            )

            href = (
                node.get(
                    "href"
                )
                or ""
            ).strip()

            if href:

                href = urljoin(
                    base_url,
                    href,
                )

                if label:
                    parts.append(
                        f"[{label}]({href})"
                    )

            elif label:
                parts.append(
                    label
                )

            return

        # -----------------------------------------
        # Line breaks
        # -----------------------------------------

        if node.name == "br":
            parts.append(
                "\n"
            )
            return

        # -----------------------------------------
        # Paragraph / list boundary
        # -----------------------------------------

        is_block = node.name in {
            "p",
            "li",
            "div",
        }

        if is_block:
            parts.append(
                "\n"
            )

        for child in node.children:
            walk(
                child
            )

        if is_block:
            parts.append(
                "\n"
            )

    walk(
        element
    )

    text = "".join(
        parts
    )

    return clean_text(
        text
    )


# =========================================================
# Main content
# =========================================================

def get_main_container(
    soup: BeautifulSoup,
) -> Tag:
    """
    Find the main page content.
    """

    candidates = [
        "main",
        "#main-content",
        ".root.container",
        "body",
    ]

    for selector in candidates:

        element = soup.select_one(
            selector
        )

        if element is not None:
            return element

    return soup


def remove_noise(
    main: Tag,
) -> None:
    """
    Remove obvious page chrome / technical elements.
    """

    noise_selectors = [
        "script",
        "style",
        "noscript",
        "template",
        "sly",
        "header",
        "footer",
        "nav",
        ".cmp-breadcrumb",
        ".cmp-navigation",
        ".website-survey",
        ".cmp-cookie"
    ]

    for selector in noise_selectors:

        for element in main.select(
            selector
        ):

            element.decompose()


# =========================================================
# Page title
# =========================================================

def extract_title(
    soup: BeautifulSoup,
    main: Tag,
) -> str:

    h1 = main.find(
        "h1"
    )

    if h1 is not None:

        title = clean_text(
            h1.get_text(
                " ",
                strip=True,
            )
        )

        if title:
            return title

    meta_title = soup.find(
        "meta",
        attrs={
            "name": "title"
        },
    )

    if meta_title:

        title = clean_text(
            meta_title.get(
                "content"
            )
        )

        if title:
            return title

    if soup.title:

        return clean_text(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )

    return ""


# =========================================================
# Images
# =========================================================

def get_image_source(
    image: Tag,
) -> str:
    """
    Get best available image source.
    """

    for attribute in [
        "src",
        "data-src",
        "data-lazy-src",
    ]:

        value = (
            image.get(
                attribute
            )
            or ""
        ).strip()

        if value:
            return value

    srcset = (
        image.get(
            "srcset"
        )
        or ""
    ).strip()

    if srcset:

        first = srcset.split(
            ","
        )[0]

        return first.strip().split(
            " "
        )[0]

    return ""


def find_image_context(
    image: Tag,
    base_url: str,
) -> tuple[
    str,
    str,
]:
    """
    Find nearby heading and nearby descriptive text.

    This is contextual metadata only.

    It is NOT used to infer the authoritative
    itinerary title.
    """

    nearby_heading = ""
    nearby_text = ""

    current = image

    for _ in range(5):

        current = current.parent

        if current is None:
            break

        if not isinstance(
            current,
            Tag,
        ):
            continue

        # -----------------------------------------
        # Standard HTML heading
        # -----------------------------------------

        heading_element = current.select_one(
            "h1, h2, h3, h4, h5, h6"
        )

        if heading_element:

            nearby_heading = clean_text(
                heading_element.get_text(
                    " ",
                    strip=True,
                )
            )

        # -----------------------------------------
        # CAG/AEM banner title fallback
        # -----------------------------------------

        if not nearby_heading:

            banner_title = current.select_one(
                ".cmp-banner__title "
                ".cmp-title__text"
            )

            if banner_title:

                nearby_heading = clean_text(
                    banner_title.get_text(
                        " ",
                        strip=True,
                    )
                )

        # -----------------------------------------
        # Nearby text
        # -----------------------------------------

        description = current.select_one(
            ".cmp-banner__description "
            ".cmp-text"
        )

        if description:

            nearby_text = (
                extract_text_with_links(
                    description,
                    base_url,
                )
            )

        if not nearby_text:

            paragraph = current.find(
                "p"
            )

            if paragraph:

                nearby_text = (
                    extract_text_with_links(
                        paragraph,
                        base_url,
                    )
                )

        if (
            nearby_heading
            or nearby_text
        ):
            break

    return (
        nearby_heading,
        nearby_text,
    )


def extract_images(
    main: Tag,
    base_url: str,
) -> list[dict]:

    images = []

    seen_urls = set()

    for image in main.find_all(
        "img"
    ):

        source = get_image_source(
            image
        )

        if not source:
            continue

        image_url = urljoin(
            base_url,
            source,
        )

        if image_url in seen_urls:
            continue

        seen_urls.add(
            image_url
        )

        (
            nearby_heading,
            nearby_text,
        ) = find_image_context(
            image,
            base_url,
        )

        images.append({
            "url": image_url,

            "alt": normalize_alt_text(
                image.get(
                    "alt",
                    "",
                )
            ),

            "nearby_heading": (
                nearby_heading
            ),

            "nearby_text": (
                nearby_text
            ),

            "links": [],
        })

    return images


# =========================================================
# FST Tour Itinerary
# =========================================================

def extract_itineraries(
    main: Tag,
    base_url: str,
) -> list[dict]:
    """
    Extract all FST timeline-slider itinerary cards.

    This is COMPONENT-BASED, not PAGE-BASED.

    Therefore it works for:

        City Sights
        Sentosa
        Heritage
        Singapore River / MBS
        ...

    as long as they use the same CAG timeline component.

    Expected source structure:

        .cmp-cardlisting--tlslider
            .swiper-slide
                .cmp-banner
                    .cmp-banner__image
                    .cmp-banner__content
                        .cmp-banner__title
                        .cmp-banner__description
    """

    itineraries = []

    seen_items = set()

    sliders = main.select(
        ".cmp-cardlisting--tlslider__container"
    )

    for (
        slider_index,
        slider,
    ) in enumerate(
        sliders,
        start=1,
    ):

        slides = slider.select(
            ".swiper-slide"
        )

        for (
            slide_index,
            slide,
        ) in enumerate(
            slides,
            start=1,
        ):

            banner = slide.select_one(
                ".cmp-banner"
            )

            if banner is None:
                continue

            # =====================================
            # Visible itinerary title
            # =====================================

            title_element = (
                banner.select_one(
                    ".cmp-banner__content "
                    ".cmp-banner__title "
                    ".cmp-title__text"
                )
            )

            title = ""

            if title_element:

                title = clean_text(
                    title_element.get_text(
                        " ",
                        strip=True,
                    )
                )

            # =====================================
            # Description
            # =====================================

            description_element = (
                banner.select_one(
                    ".cmp-banner__description "
                    ".cmp-text"
                )
            )

            description = ""

            if description_element:

                description = (
                    extract_text_with_links(
                        description_element,
                        base_url,
                    )
                )

            # =====================================
            # Image
            # =====================================

            image_url = ""
            image_alt = ""

            image_container = (
                banner.select_one(
                    ".cmp-banner__image"
                )
            )

            if image_container:

                # ---------------------------------
                # Prefer original AEM asset path
                # ---------------------------------

                asset_element = (
                    image_container.select_one(
                        ".cmp-image[data-asset]"
                    )
                )

                if asset_element:

                    data_asset = (
                        asset_element.get(
                            "data-asset"
                        )
                        or ""
                    ).strip()

                    if data_asset:

                        image_url = urljoin(
                            base_url,
                            data_asset,
                        )

                # ---------------------------------
                # Preserve alt independently
                # ---------------------------------

                image_element = (
                    image_container.select_one(
                        "img"
                    )
                )

                if image_element:

                    image_alt = (
                        normalize_alt_text(
                            image_element.get(
                                "alt",
                                "",
                            )
                        )
                    )

                    # Fallback
                    if not image_url:

                        image_source = (
                            get_image_source(
                                image_element
                            )
                        )

                        if image_source:

                            image_url = urljoin(
                                base_url,
                                image_source,
                            )

            # =====================================
            # Skip empty component
            # =====================================

            if (
                not title
                and not description
            ):
                continue

            # =====================================
            # Swiper can clone slides.
            # Deduplicate them.
            # =====================================

            dedup_key = (
                title.lower(),
                description.lower(),
                image_url,
            )

            if dedup_key in seen_items:
                continue

            seen_items.add(
                dedup_key
            )

            itineraries.append({
                "index": (
                    len(
                        itineraries
                    )
                    + 1
                ),

                "title": title,

                "description": (
                    description
                ),

                "image": {
                    "url": image_url,
                    "alt": image_alt,
                },

                "source_component": (
                    "cmp-cardlisting--tlslider"
                ),

                "slider_index": (
                    slider_index
                ),

                "slide_index": (
                    slide_index
                ),
            })

    return itineraries


# =========================================================
# Registration Details
# =========================================================

def extract_registration_details(
    main: Tag,
    base_url: str,
) -> dict | None:
    """
    Extract the FST Registration Details component.

    Example structure:

        Registration Details
            Service Counters
                intro
                Terminal 2
                Terminal 3
                Other Terminals

            Required Documents
                Passport...
    """

    title_element = None

    # =============================================
    # Find Registration Details visual title
    # =============================================

    for element in main.select(
        ".cmp-banner__title "
        ".cmp-title__text"
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if (
            text.lower()
            == "registration details"
        ):

            title_element = element
            break

    if title_element is None:
        return None

    title = clean_text(
        title_element.get_text(
            " ",
            strip=True,
        )
    )

    # =============================================
    # Find nearest AEM grid containing title + body
    # =============================================

    grid = title_element.find_parent(
        "div",
        class_=lambda classes: (
            classes
            and "aem-Grid"
            in (
                classes
                if isinstance(
                    classes,
                    list,
                )
                else str(
                    classes
                ).split()
            )
        ),
    )

    if grid is None:
        return None

    text_blocks = grid.select(
        ".text .cmp-text"
    )

    if not text_blocks:
        return None

    subsections = []

    # Registration body should normally be
    # the first meaningful text block.
    for text_block in text_blocks:

        current_section = None

        found_registration_content = False

        for child in text_block.find_all(
            ["p", "ul", "ol"],
            recursive=False,
        ):

            # =====================================
            # Paragraph
            # =====================================

            if child.name == "p":

                full_text = (
                    extract_text_with_links(
                        child,
                        base_url,
                    )
                )

                if not full_text:
                    continue

                # FST has:
                #
                # <p>
                #   <b><u>Service Counters</u></b>
                #   Please stay...
                # </p>

                heading_element = (
                    child.select_one(
                        "b u, u b"
                    )
                )

                if heading_element:

                    heading = clean_text(
                        heading_element.get_text(
                            " ",
                            strip=True,
                        )
                    )

                    if not heading:
                        continue

                    body = full_text

                    if body.lower().startswith(
                        heading.lower()
                    ):

                        body = body[
                            len(
                                heading
                            ):
                        ].strip()

                    current_section = {
                        "title": heading,
                        "content": body,
                        "items": [],
                    }

                    subsections.append(
                        current_section
                    )

                    found_registration_content = True

                    continue

                # Plain continuation paragraph
                if current_section:

                    if current_section[
                        "content"
                    ]:

                        current_section[
                            "content"
                        ] += (
                            "\n\n"
                            + full_text
                        )

                    else:

                        current_section[
                            "content"
                        ] = full_text

            # =====================================
            # Bullet list
            # =====================================

            elif child.name in {
                "ul",
                "ol",
            }:

                if current_section is None:
                    continue

                for li in child.find_all(
                    "li",
                    recursive=False,
                ):

                    full_text = (
                        extract_text_with_links(
                            li,
                            base_url,
                        )
                    )

                    if not full_text:
                        continue

                    label_element = li.find(
                        "b"
                    )

                    label = ""

                    if label_element:

                        label = clean_text(
                            label_element.get_text(
                                " ",
                                strip=True,
                            )
                        )

                        label = (
                            label.rstrip(
                                ":"
                            )
                        )

                    item_content = full_text

                    if (
                        label
                        and item_content
                        .lower()
                        .startswith(
                            label.lower()
                        )
                    ):

                        item_content = (
                            item_content[
                                len(
                                    label
                                ):
                            ]
                            .lstrip(
                                ": "
                            )
                            .strip()
                        )

                    current_section[
                        "items"
                    ].append({
                        "label": label,
                        "content": (
                            item_content
                        ),
                    })

        if found_registration_content:
            break

    if not subsections:
        return None

    return {
        "title": title,
        "subsections": (
            subsections
        ),
    }


# =========================================================
# Tables
# =========================================================

def extract_tables(
    main: Tag,
    base_url: str,
) -> list[dict]:

    tables = []

    for (
        index,
        table,
    ) in enumerate(
        main.find_all(
            "table"
        ),
        start=1,
    ):

        headers = []

        rows = []

        header_cells = table.find_all(
            "th"
        )

        if header_cells:

            headers = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell
                in header_cells
            ]

        for row in table.find_all(
            "tr"
        ):

            cells = row.find_all(
                ["td", "th"]
            )

            values = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell
                in cells
            ]

            if any(
                values
            ):
                rows.append(
                    values
                )

        if not rows:
            continue

        # -----------------------------------------
        # Capture note immediately after table
        # -----------------------------------------

        notes = []

        parent_text_component = table.find_parent(
            class_="cmp-text"
        )

        if parent_text_component:

            for sibling in table.find_next_siblings(
                "p"
            ):

                note = (
                    extract_text_with_links(
                        sibling,
                        base_url,
                    )
                )

                if note:
                    notes.append(
                        note
                    )

        tables.append({
            "caption": (
                f"Table {index}"
            ),

            "headers": headers,

            "rows": rows,

            "notes": notes,
        })

    return tables


# =========================================================
# Accordions
# =========================================================

def extract_accordions(
    main: Tag,
    base_url: str,
) -> list[dict]:
    """
    Generic CAG/AEM accordion extraction.

    This remains intentionally broad because different
    CAG pages can use slightly different accordion wrappers.
    """

    accordions = []

    seen = set()

    selectors = [
        ".cmp-accordion__item",
        "[class*='accordion'] .cmp-accordion__item",
    ]

    candidates = []

    for selector in selectors:

        candidates.extend(
            main.select(
                selector
            )
        )

    for item in candidates:

        title_element = item.select_one(
            ".cmp-accordion__header, "
            ".cmp-accordion__button, "
            ".cmp-accordion__title"
        )

        content_element = item.select_one(
            ".cmp-accordion__panel, "
            ".cmp-accordion__content"
        )

        if not title_element:
            continue

        title = clean_text(
            title_element.get_text(
                " ",
                strip=True,
            )
        )

        if not title:
            continue

        content = ""

        if content_element:

            content = (
                extract_text_with_links(
                    content_element,
                    base_url,
                )
            )

        key = (
            title.lower(),
            content.lower(),
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        accordions.append({
            "title": title,

            "heading_path": [
                title
            ],

            "content": content,
        })

    return accordions


# =========================================================
# Tabs
# =========================================================

def extract_tabs(
    main: Tag,
    base_url: str,
) -> list[dict]:

    tabs = []

    tab_lists = main.select(
        ".cmp-tabs"
    )

    for (
        tab_group_index,
        tab_group,
    ) in enumerate(
        tab_lists,
        start=1,
    ):

        tab_buttons = tab_group.select(
            ".cmp-tabs__tab"
        )

        tab_panels = tab_group.select(
            ".cmp-tabs__tabpanel"
        )

        for index, panel in enumerate(
            tab_panels
        ):

            title = (
                clean_text(
                    tab_buttons[
                        index
                    ].get_text(
                        " ",
                        strip=True,
                    )
                )
                if index
                < len(
                    tab_buttons
                )
                else (
                    f"Tab "
                    f"{index + 1}"
                )
            )

            content = (
                extract_text_with_links(
                    panel,
                    base_url,
                )
            )

            tabs.append({
                "title": title,

                "content": (
                    content
                ),

                "tab_group_index": (
                    tab_group_index
                ),

                "sections": [],

                "accordions": (
                    extract_accordions(
                        panel,
                        base_url,
                    )
                ),

                "tables": (
                    extract_tables(
                        panel,
                        base_url,
                    )
                ),
            })

    return tabs


# =========================================================
# Generic sections
# =========================================================

def extract_sections(
    main: Tag,
    base_url: str,
    heading_prefix: list[str] | None = None,
) -> list[dict]:
    """
    Generic heading-based extraction.

    This intentionally remains generic.

    More semantically rich CAG components such as
    registration_details and itineraries are separately
    extracted into dedicated structures.
    """

    heading_prefix = (
        heading_prefix
        or []
    )

    sections = []

    headings = main.find_all(
        [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        ]
    )

    if not headings:

        content = (
            extract_text_with_links(
                main,
                base_url,
            )
        )

        if content:

            sections.append({
                "heading": (
                    heading_prefix[
                        -1
                    ]
                    if heading_prefix
                    else ""
                ),

                "heading_level": 1,

                "heading_path": (
                    heading_prefix
                ),

                "content": [
                    content
                ],

                "links": [],
            })

        return sections

    for heading in headings:

        heading_text = clean_text(
            heading.get_text(
                " ",
                strip=True,
            )
        )

        if not heading_text:
            continue

        try:

            level = int(
                heading.name[
                    1
                ]
            )

        except Exception:

            level = 1

        content_items = []

        current = (
            heading.next_sibling
        )

        while current is not None:

            if (
                isinstance(
                    current,
                    Tag,
                )
                and current.name
                in {
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                }
            ):
                break

            if isinstance(
                current,
                Tag,
            ):

                # Tables/images are handled separately.
                if current.name == "table":

                    current = (
                        current.next_sibling
                    )

                    continue

                text = (
                    extract_text_with_links(
                        current,
                        base_url,
                    )
                )

                if text:
                    content_items.append(
                        text
                    )

            elif isinstance(
                current,
                NavigableString,
            ):

                text = clean_text(
                    str(
                        current
                    )
                )

                if text:
                    content_items.append(
                        text
                    )

            current = (
                current.next_sibling
            )

        if not content_items:
            continue

        # Deduplicate exact items
        unique_content = []

        seen_content = set()

        for item in content_items:

            key = re.sub(
                r"\s+",
                " ",
                item.lower(),
            ).strip()

            if (
                not key
                or key
                in seen_content
            ):
                continue

            seen_content.add(
                key
            )

            unique_content.append(
                item
            )

        sections.append({
            "heading": (
                heading_text
            ),

            "heading_level": (
                level
            ),

            "heading_path": (
                heading_prefix[
                    :-1
                ]
                + [
                    heading_text
                ]
                if heading_prefix
                else [
                    heading_text
                ]
            ),

            "content": (
                unique_content
            ),

            "links": [],
        })

    return sections


# =========================================================
# Links
# =========================================================

def extract_links(
    main: Tag,
    base_url: str,
) -> list[dict]:

    links = []

    seen = set()

    for anchor in main.find_all(
        "a"
    ):

        href = (
            anchor.get(
                "href"
            )
            or ""
        ).strip()

        if not href:
            continue

        if href.startswith(
            "#"
        ):
            continue

        text = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        url = urljoin(
            base_url,
            href,
        )

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
# Extract one page
# =========================================================

def extract_page(
    page_config: dict,
) -> dict:

    page_id = page_config[
        "id"
    ]

    raw_page_dir = (
        RAW_WEB_DIR
        / page_id
    )

    html_path = (
        raw_page_dir
        / "page.html"
    )

    if not html_path.exists():

        raise FileNotFoundError(
            f"Missing HTML for "
            f"{page_id}: "
            f"{html_path}"
        )

    html = html_path.read_text(
        encoding="utf-8"
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    main = get_main_container(
        soup
    )

    # Work on copy so original soup remains intact.
    main_clean = deepcopy(
        main
    )

    remove_noise(
        main_clean
    )

    base_url = page_config[
        "url"
    ]

    title = extract_title(
        soup,
        main_clean,
    )

    # =====================================================
    # Structured components
    # =====================================================

    registration_details = (
        extract_registration_details(
            main_clean,
            base_url,
        )
    )

    itineraries = (
        extract_itineraries(
            main_clean,
            base_url,
        )
    )

    tables = extract_tables(
        main_clean,
        base_url,
    )

    accordions = (
        extract_accordions(
            main_clean,
            base_url,
        )
    )

    tabs = extract_tabs(
        main_clean,
        base_url,
    )

    images = extract_images(
        main_clean,
        base_url,
    )

    links = extract_links(
        main_clean,
        base_url,
    )

    sections = extract_sections(
        main_clean,
        base_url,
        heading_prefix=[
            title
        ],
    )

    # =====================================================
    # Output
    # =====================================================

    output = {
        "extractor_version": (
            EXTRACTOR_VERSION
        ),

        "id": page_id,

        "name": page_config[
            "name"
        ],

        "page_type": (
            page_config.get(
                "page_type",
                "tour",
            )
        ),

        "url": base_url,

        "title": title,

        "sections": (
            sections
        ),

        "registration_details": (
            registration_details
        ),

        "itineraries": (
            itineraries
        ),

        "tabs": (
            tabs
        ),

        "accordions": (
            accordions
        ),

        "tables": (
            tables
        ),

        "images": (
            images
        ),

        "links": (
            links
        ),

        "extraction_summary": {
            "section_count": len(
                sections
            ),

            "registration_subsection_count": (
                len(
                    registration_details.get(
                        "subsections",
                        [],
                    )
                )
                if registration_details
                else 0
            ),

            "itinerary_count": len(
                itineraries
            ),

            "tab_count": len(
                tabs
            ),

            "accordion_count": len(
                accordions
            ),

            "table_count": len(
                tables
            ),

            "image_count": len(
                images
            ),

            "link_count": len(
                links
            ),
        },
    }

    return output


# =========================================================
# Save
# =========================================================

def save_page(
    data: dict,
) -> Path:

    output_path = (
        PROCESSED_WEB_DIR
        / f"{data['id']}.json"
    )

    output_path.write_text(
        json.dumps(
            data,
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

    report = []

    for page_config in PAGES:

        page_id = page_config[
            "id"
        ]

        print(
            f"\nExtracting: "
            f"{page_id}"
        )

        try:

            data = extract_page(
                page_config
            )

            output_path = save_page(
                data
            )

            report.append({
                "id": page_id,
                "status": "success",
                "output": str(
                    output_path
                ),
                "summary": (
                    data[
                        "extraction_summary"
                    ]
                ),
            })

            print(
                f"  Saved: "
                f"{output_path}"
            )

            print(
                "  Summary:",
                data[
                    "extraction_summary"
                ],
            )

        except Exception as exc:

            report.append({
                "id": page_id,
                "status": "failed",
                "error": str(
                    exc
                ),
            })

            print(
                f"  FAILED: {exc}"
            )

    report_path = (
        PROCESSED_WEB_DIR
        / "extraction_report.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "\nExtraction completed."
    )

    print(
        f"Report: "
        f"{report_path}"
    )


if __name__ == "__main__":
    main()