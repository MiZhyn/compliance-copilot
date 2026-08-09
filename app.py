# app.py

from __future__ import annotations

import streamlit as st

from ui.live_demo import (
    render_live_demo,
)

from ui.resources import (
    get_travel_copilot,
)

from ui.styles import (
    apply_global_styles,
)


# =========================================================
# Page config
# =========================================================

st.set_page_config(
    page_title="Travel & Compliance Copilot",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# Global style
# =========================================================

apply_global_styles()


# =========================================================
# Warm up the AI engine
#
# First app load:
#   BGE / Chroma / BM25 / Reranker / Planner
#
# Following reruns:
#   returned from @st.cache_resource
# =========================================================

get_travel_copilot()


# =========================================================
# Application
# =========================================================

render_live_demo()