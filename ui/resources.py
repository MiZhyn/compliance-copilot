# ui/resources.py

from __future__ import annotations

import streamlit as st

from src.orchestration.travel_copilot import (
    TravelCopilot,
)


# =========================================================
# Global AI resource
# =========================================================

@st.cache_resource(
    show_spinner="Preparing AI engine..."
)
def get_travel_copilot() -> TravelCopilot:
    """
    Initialise the expensive AI stack only once.

    Cached resources include:

    - BGE embedding model
    - Chroma vector store
    - BM25 retrieval index
    - parent document store
    - Claude reranker
    - TravelPlanner
    - database repositories
    - final synthesis model

    Streamlit reruns will reuse the same instance.
    """

    return TravelCopilot()