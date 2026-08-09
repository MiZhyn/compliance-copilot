from __future__ import annotations

import asyncio
import json
import re

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import (
    unquote,
    urldefrag,
    urlparse,
    urlunparse,
)

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from .config import (
    ALLOWED_LINK_PATTERNS,
    PAGES,
)


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[4]

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


# =========================================================
# Fetch configuration
# =========================================================

NAVIGATION_TIMEOUT_MS = 60_000

CONTENT_TIMEOUT_MS = 30_000

MAX_RETRIES = 3

REQUEST_DELAY_SECONDS = 1.0


# =========================================================
# Utilities
# =========================================================

def utc_now() -> str:
    """
    Current UTC timestamp for manifest tracking.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(
    value: str | None,
) -> str:

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value.replace(
            "\xa0",
            " ",
        ),
    ).strip()


def slugify(
    value: str,
) -> str:
    """
    Convert a URL path segment into a stable page id.

    Example:

        Democratic People's Republic of Korea

    becomes:

        democratic-people-s-republic-of-korea
    """

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


def canonicalise_url(
    url: str,
) -> str:
    """
    Canonicalise ICA HTML page URLs.

    Removes:
    - fragments
    - tracking query parameters
    - trailing slash

    This prevents duplicate fetches such as:

        page?a=1
        page#section
        page/
    """

    url, _ = urldefrag(
        url
    )

    parsed = urlparse(
        url
    )

    return urlunparse(
        (
            parsed.scheme.lower(),

            parsed.netloc.lower(),

            parsed.path.rstrip(
                "/"
            )
            or "/",

            "",

            "",

            "",
        )
    )


def page_id_from_url(
    url: str,
) -> str:
    """
    Generate page id from final URL path segment.

    unquote() is important because URLs can contain
    encoded characters such as %27.
    """

    path_parts = [
        part
        for part
        in urlparse(
            url
        ).path.split(
            "/"
        )
        if part
    ]

    if not path_parts:
        return "index"

    final_part = unquote(
        path_parts[-1]
    )

    return slugify(
        final_part
    )


def relative_project_path(
    path: Path,
) -> str:

    return path.relative_to(
        PROJECT_ROOT
    ).as_posix()


# =========================================================
# URL filtering
# =========================================================

def is_allowed_child_url(
    url: str,
    seed_url: str,
) -> bool:
    """
    Decide whether a discovered link belongs to the
    ICA Visa dataset.

    We accept only:
    - ICA domain
    - visa requirement child pages
    - Visa-Free Transit Facility

    PDFs and the seed page itself are excluded.
    """

    url = canonicalise_url(
        url
    )

    seed_url = canonicalise_url(
        seed_url
    )

    parsed = urlparse(
        url
    )

    # -----------------------------------------
    # Do not fetch seed twice
    # -----------------------------------------

    if url == seed_url:
        return False

    # -----------------------------------------
    # Only HTTP(S)
    # -----------------------------------------

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return False

    # -----------------------------------------
    # ICA domain only
    # -----------------------------------------

    if parsed.netloc.lower() not in {
        "www.ica.gov.sg",
        "ica.gov.sg",
    }:
        return False

    # -----------------------------------------
    # PDFs are not part of this HTML ingestion
    # pipeline.
    #
    # We can ingest PDFs separately later.
    # -----------------------------------------

    if parsed.path.lower().endswith(
        ".pdf"
    ):
        return False

    path_lower = (
        parsed.path.lower()
    )

    return any(
        pattern.lower()
        in path_lower

        for pattern
        in ALLOWED_LINK_PATTERNS
    )


# =========================================================
# File saving
# =========================================================

def save_html(
    page_id: str,
    html: str,
) -> Path:
    """
    Atomically save rendered page HTML.
    """

    HTML_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        HTML_DIR
        / f"{page_id}.html"
    )

    temporary_path = (
        output_path.with_suffix(
            ".html.tmp"
        )
    )

    temporary_path.write_text(
        html,
        encoding="utf-8",
    )

    temporary_path.replace(
        output_path
    )

    return output_path


# =========================================================
# Page readiness
# =========================================================

async def wait_for_page(
    page: Page,
    wait_selector: str,
    ready_selector: str | None = None,
) -> None:
    """
    Wait until the ICA page has rendered enough content
    for extraction / link discovery.

    wait_selector:
        Basic page presence, usually body.

    ready_selector:
        Source-specific indication that important
        dynamic content has appeared.
    """

    await page.wait_for_selector(
        wait_selector,
        state="attached",
        timeout=CONTENT_TIMEOUT_MS,
    )

    if ready_selector:

        await page.wait_for_selector(
            ready_selector,
            state="attached",
            timeout=CONTENT_TIMEOUT_MS,
        )

    # Some ICA analytics requests remain active,
    # so networkidle is best-effort only.
    try:

        await page.wait_for_load_state(
            "networkidle",
            timeout=10_000,
        )

    except PlaywrightTimeoutError:
        pass


# =========================================================
# Fetch one page
# =========================================================

async def fetch_page(
    page: Page,
    page_id: str,
    url: str,
    wait_selector: str = "body",
    ready_selector: str | None = None,
) -> dict[str, Any]:
    """
    Fetch one ICA page and save rendered HTML.
    """

    url = canonicalise_url(
        url
    )

    last_error: Exception | None = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            print(
                f"Fetching: {url}",
                flush=True,
            )

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT_MS,
            )

            if response is None:

                raise RuntimeError(
                    "No HTTP response received."
                )

            if response.status >= 400:

                raise RuntimeError(
                    f"HTTP {response.status}"
                )

            await wait_for_page(
                page=page,

                wait_selector=(
                    wait_selector
                ),

                ready_selector=(
                    ready_selector
                ),
            )

            final_url = (
                canonicalise_url(
                    page.url
                )
            )

            html_path = save_html(
                page_id=page_id,

                html=await page.content(),
            )

            print(
                f"  Saved: "
                f"{html_path.name}",
                flush=True,
            )

            return {
                "page_id": page_id,

                "url": final_url,

                "html_path": (
                    relative_project_path(
                        html_path
                    )
                ),

                "http_status": (
                    response.status
                ),

                "fetch_status": (
                    "success"
                ),
            }

        except Exception as exc:

            last_error = exc

            print(
                (
                    f"  Attempt "
                    f"{attempt}/"
                    f"{MAX_RETRIES} "
                    f"failed: {exc}"
                ),
                flush=True,
            )

            if attempt < MAX_RETRIES:

                await asyncio.sleep(
                    attempt * 2
                )

    return {
        "page_id": page_id,

        "url": url,

        "fetch_status": "failed",

        "error": str(
            last_error
        ),
    }


# =========================================================
# Child page discovery
# =========================================================

async def discover_child_pages(
    page: Page,
    seed_url: str,
) -> list[dict[str, str]]:
    """
    Discover eligible ICA Visa child pages from the
    fully rendered seed page.

    IMPORTANT:

    We intentionally inspect ALL anchor tags first,
    then apply URL allow-list filtering.

    Therefore discovery is controlled by URL structure,
    not by visible country names or hardcoded countries.
    """

    raw_links = await page.locator(
        "a[href]"
    ).evaluate_all(
        """
        anchors => anchors.map(anchor => ({
            url: anchor.href,

            text: (
                anchor.innerText
                || anchor.textContent
                || ""
            )
            .replace(/\\s+/g, " ")
            .trim()
        }))
        """
    )

    targets_by_url: dict[
        str,
        dict[str, str],
    ] = {}

    for link in raw_links:

        url = clean_text(
            link.get(
                "url"
            )
        )

        link_text = clean_text(
            link.get(
                "text"
            )
        )

        if not url:
            continue

        if not is_allowed_child_url(
            url,
            seed_url,
        ):
            continue

        url = canonicalise_url(
            url
        )

        targets_by_url[
            url
        ] = {
            "page_id": (
                page_id_from_url(
                    url
                )
            ),

            "url": url,

            # Useful provenance for later debugging.
            "link_text": (
                link_text
            ),
        }

    return sorted(
        targets_by_url.values(),

        key=lambda item: (
            item[
                "page_id"
            ]
        ),
    )


# =========================================================
# Main fetch pipeline
# =========================================================

async def main() -> None:

    HTML_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[
        dict[str, Any]
    ] = []

    started_at = utc_now()

    async with async_playwright() as playwright:

        browser = (
            await playwright.chromium.launch(
                headless=True
            )
        )

        context = (
            await browser.new_context(
                viewport={
                    "width": 1440,
                    "height": 1200,
                },

                locale="en-SG",
            )
        )

        page = await context.new_page()

        # =================================================
        # Seed pages
        # =================================================

        for config in PAGES:

            seed_url = (
                canonicalise_url(
                    config[
                        "url"
                    ]
                )
            )

            seed_result = (
                await fetch_page(
                    page=page,

                    page_id=config[
                        "id"
                    ],

                    url=seed_url,

                    wait_selector=(
                        config.get(
                            "wait_selector",
                            "body",
                        )
                    ),

                    ready_selector=(
                        config.get(
                            "ready_selector"
                        )
                    ),
                )
            )

            results.append(
                seed_result
            )

            if (
                seed_result[
                    "fetch_status"
                ]
                != "success"

                or not config.get(
                    "discover_links",
                    False,
                )
            ):
                continue

            # =================================================
            # Discover child pages from rendered seed DOM
            # =================================================

            child_pages = (
                await discover_child_pages(
                    page=page,
                    seed_url=seed_url,
                )
            )

            print(
                (
                    "Discovered child pages: "
                    f"{len(child_pages)}"
                ),
                flush=True,
            )

            # =================================================
            # Fetch child pages
            # =================================================

            for index, child in enumerate(
                child_pages,
                start=1,
            ):

                print(
                    (
                        f"[{index}/"
                        f"{len(child_pages)}] "
                        f"{child['page_id']}"
                    ),
                    flush=True,
                )

                if child.get(
                    "link_text"
                ):

                    print(
                        (
                            "  Link text: "
                            f"{child['link_text']}"
                        ),
                        flush=True,
                    )

                result = (
                    await fetch_page(
                        page=page,

                        page_id=(
                            child[
                                "page_id"
                            ]
                        ),

                        url=(
                            child[
                                "url"
                            ]
                        ),
                    )
                )

                # Preserve discovery metadata
                result[
                    "discovered_from"
                ] = seed_url

                result[
                    "link_text"
                ] = child.get(
                    "link_text",
                    "",
                )

                results.append(
                    result
                )

                await asyncio.sleep(
                    REQUEST_DELAY_SECONDS
                )

        await context.close()

        await browser.close()

    # =====================================================
    # Manifest
    # =====================================================

    successful_count = sum(
        result[
            "fetch_status"
        ]
        == "success"

        for result
        in results
    )

    manifest = {
        "source": "ica",

        "dataset": (
            "visa_requirements"
        ),

        "started_at": (
            started_at
        ),

        "completed_at": (
            utc_now()
        ),

        "total_count": len(
            results
        ),

        "successful_count": (
            successful_count
        ),

        "failed_count": (
            len(results)
            - successful_count
        ),

        "pages": (
            results
        ),
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "\nFetch completed.",
        flush=True,
    )

    print(
        f"HTML folder: "
        f"{HTML_DIR}",
        flush=True,
    )

    print(
        f"Manifest: "
        f"{MANIFEST_PATH}",
        flush=True,
    )

    print(
        f"Successful: "
        f"{successful_count}",
        flush=True,
    )

    print(
        (
            f"Failed: "
            f"{len(results) - successful_count}"
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )