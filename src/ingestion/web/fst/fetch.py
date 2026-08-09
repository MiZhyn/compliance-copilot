import json
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from .config import PAGES


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[4]

RAW_WEB_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "web"
    / "fst"
)

RAW_WEB_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Page loading
# ---------------------------------------------------------

def wait_for_page(page: Page) -> None:
    """
    Wait until the important page content is loaded.
    """

    page.wait_for_load_state("domcontentloaded")

    try:
        page.wait_for_load_state(
            "networkidle",
            timeout=15_000,
        )
    except Exception:
        print(
            "  Network did not become fully idle. "
            "Continuing."
        )


def scroll_through_page(page: Page) -> None:
    """
    Scroll through the page so lazy-loaded content is loaded.
    """

    for _ in range(20):

        current_height = page.evaluate(
            "document.body.scrollHeight"
        )

        page.evaluate(
            "window.scrollTo(0, document.body.scrollHeight)"
        )

        time.sleep(0.5)

        new_height = page.evaluate(
            "document.body.scrollHeight"
        )

        if new_height <= current_height:
            break

    page.evaluate("window.scrollTo(0, 0)")


def expand_accordions(page: Page) -> None:
    """
    Expand FAQ and accordion sections so their content
    appears in the final HTML.
    """

    main = page.locator("main")

    if main.count() == 0:
        main = page.locator("body")

    buttons = main.locator(
        "button[aria-expanded='false']"
    )

    button_count = buttons.count()

    for index in range(button_count):

        try:
            button = buttons.nth(index)

            if not button.is_visible():
                continue

            button.scroll_into_view_if_needed()

            button.click(
                timeout=5_000
            )

            time.sleep(0.3)

        except Exception as exc:
            print(
                f"  Could not open accordion "
                f"{index}: {exc}"
            )


# ---------------------------------------------------------
# Save raw source
# ---------------------------------------------------------

def save_page(
    page: Page,
    page_config: dict,
) -> None:
    """
    Save raw HTML and source metadata.
    """

    page_id = page_config["id"]

    output_dir = (
        RAW_WEB_DIR
        / page_id
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Raw HTML
    html_path = (
        output_dir
        / "page.html"
    )

    html_path.write_text(
        page.content(),
        encoding="utf-8",
    )

    # Source metadata
    metadata = {
        "id": page_id,
        "name": page_config["name"],
        "page_type": page_config["page_type"],
        "requested_url": page_config["url"],
        "final_url": page.url,
        "browser_title": page.title(),
        "collected_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    metadata_path = (
        output_dir
        / "metadata.json"
    )

    metadata_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"  Saved HTML: {html_path}"
    )


# ---------------------------------------------------------
# Fetch one page
# ---------------------------------------------------------

def collect_page(
    page: Page,
    page_config: dict,
) -> None:

    print(
        f"\nCollecting: "
        f"{page_config['name']}"
    )

    response = page.goto(
        page_config["url"],
        wait_until="domcontentloaded",
        timeout=60_000,
    )

    if response is None:
        raise RuntimeError(
            "Browser did not receive a response."
        )

    if response.status >= 400:
        raise RuntimeError(
            f"Page returned HTTP "
            f"{response.status}"
        )

    wait_for_page(page)

    scroll_through_page(page)

    expand_accordions(page)

    # Accordion expansion may create additional
    # lazy-loaded content.
    scroll_through_page(page)

    save_page(
        page=page,
        page_config=page_config,
    )


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

def main() -> None:

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=False
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        page = context.new_page()

        for page_config in PAGES:

            try:
                collect_page(
                    page=page,
                    page_config=page_config,
                )

            except Exception as exc:

                print(
                    f"  Failed: "
                    f"{page_config['id']} - {exc}"
                )

        browser.close()

        print(
            "\nFST web collection completed."
        )


if __name__ == "__main__":
    main()