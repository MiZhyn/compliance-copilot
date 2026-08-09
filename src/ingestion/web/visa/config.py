PAGES = [
    {
        "id": "ica_visa_requirements",
        "name": "ICA Visa Requirements",
        "source": "ica",
        "page_type": "visa_index",

        "url": (
            "https://www.ica.gov.sg/"
            "enter-transit-depart/"
            "entering-singapore/"
            "visa_requirements"
        ),

        "wait_selector": "body",

        # Wait until country/place links appear
        "content_selector": (
            "a[href*='visa-detail-page']"
        ),

        "discover_links": True,
    }
]


ALLOWED_LINK_PATTERNS = [
    (
        "/enter-transit-depart/"
        "entering-singapore/"
        "visa_requirements/"
        "visa-detail-page/"
    ),
]