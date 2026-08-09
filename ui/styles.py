# ui/styles.py

from __future__ import annotations

from textwrap import dedent

import streamlit as st


# =========================================================
# HTML helper
# =========================================================

def render_html(
    content: str,
) -> None:
    """
    Render custom HTML without Markdown interpreting
    multiline indentation as code.
    """

    st.html(
        dedent(
            content
        ).strip()
    )


# =========================================================
# Global CSS
# =========================================================

def apply_global_styles() -> None:

    st.html(
        """
        <style>

        /* =================================================
           PAGE
        ================================================= */

        .stApp {
            background: #f8f9fb;
        }

        .block-container {
            max-width: 1050px;

            padding-top: 2.2rem;
            padding-bottom: 9rem;

            padding-left: 2rem;
            padding-right: 2rem;
        }


        /* =================================================
           STREAMLIT TOP BAR
        ================================================= */

        [data-testid="stHeader"] {
            background: transparent;
        }

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }


        /* =================================================
           APP HEADER
        ================================================= */

        .copilot-header {
            padding:
                4px
                0
                20px
                0;
        }

        .copilot-brand {
            display: flex;

            align-items: center;

            gap: 11px;
        }

        .copilot-logo {
            display: flex;

            align-items: center;
            justify-content: center;

            width: 38px;
            height: 38px;

            border-radius: 10px;

            background: #ffffff;

            border:
                1px solid
                rgba(15, 23, 42, 0.08);

            font-size: 20px;
        }

        .copilot-title {
            font-size: 26px;

            font-weight: 720;

            line-height: 1.2;

            letter-spacing: -0.02em;
        }

        .copilot-subtitle {
            margin-top: 7px;

            margin-left: 49px;

            max-width: 720px;

            font-size: 14px;

            line-height: 1.5;

            color: #64748b;
        }


        /* =================================================
           QUICK ACTION AREA
        ================================================= */

        .quick-label {
            margin-top: 4px;
            margin-bottom: 7px;

            font-size: 12px;

            font-weight: 600;

            text-transform: uppercase;

            letter-spacing: 0.055em;

            color: #94a3b8;
        }


        /* =================================================
           CHAT MESSAGE BASE
        ================================================= */

        [data-testid="stChatMessage"] {

            background: transparent;

            border: none;

            gap: 0.55rem;

            padding-top: 0.45rem;
            padding-bottom: 0.9rem;

            align-items: flex-start;
        }


        /* Remove unnecessary outer ChatMessage spacing */

        [data-testid="stChatMessageContent"] {

            line-height: 1.60;

            font-size: 15px;
        }


        /* =================================================
           ASSISTANT — FULL-WIDTH ANSWER (no bubble)

           The assistant reply and the structured panels
           below it (Journey / FST / expanders) share one
           left-aligned, equal-width column so they read
           as a single answer instead of "narrow bubble +
           wide table".
        ================================================= */

        [data-testid="stChatMessage"]:has(
            .chat-assistant-marker
        ) {

            flex-direction: row;
        }


        /* Answer fills the space to the right of the avatar
           (flex:1) instead of dropping onto its own line,
           and keeps the avatar sitting right beside it. */

        [data-testid="stChatMessage"]:has(
            .chat-assistant-marker
        )
        [data-testid="stChatMessageContent"] {

            flex: 1;

            min-width: 0;

            padding:
                2px
                0;

            background: transparent;

            border: none;

            border-radius: 0;

            box-shadow: none;
        }


        /* =================================================
           USER — RIGHT
        ================================================= */

        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        ) {

            flex-direction: row-reverse;

            justify-content: flex-start;
        }


        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        )
        [data-testid="stChatMessageContent"] {

            width: fit-content;

            max-width: 70%;

            padding:
                13px
                18px;

            background: #eaf2ff;

            border:
                1px solid
                rgba(59, 130, 246, 0.10);

            border-radius:
                18px
                6px
                18px
                18px;
        }


        /* Key fix (version-proof): the direct child block
           wrapper, not a testid, so the bubble hugs the
           text width across Streamlit versions. margin:0
           stops inner elements from eating the padding. */

        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        )
        [data-testid="stChatMessageContent"] > div {

            width: fit-content;

            max-width: 100%;

            margin: 0;
        }

        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        )
        [data-testid="stChatMessageContent"] p {

            margin: 0;
        }


        /* =================================================
           HIDE CSS MARKERS
        ================================================= */

        .chat-user-marker,
        .chat-assistant-marker {
            display: none;
        }


        /* =================================================
           CHAT MARKDOWN
        ================================================= */

        [data-testid="stChatMessageContent"] p {

            margin-top: 0;
            margin-bottom: 0.65rem;
        }

        [data-testid="stChatMessageContent"] p:last-child {

            margin-bottom: 0;
        }

        [data-testid="stChatMessageContent"] h1,
        [data-testid="stChatMessageContent"] h2,
        [data-testid="stChatMessageContent"] h3 {

            margin-top: 0.8rem;
            margin-bottom: 0.45rem;
        }

        [data-testid="stChatMessageContent"] h3 {

            font-size: 16px;
        }

        [data-testid="stChatMessageContent"] ul {

            margin-top: 0.35rem;
            margin-bottom: 0.45rem;
        }


        /* =================================================
           CHAT INPUT
        ================================================= */

        [data-testid="stChatInput"] {

            border-radius: 16px;

            border:
                1px solid
                rgba(15, 23, 42, 0.10);

            background: #ffffff;

            box-shadow:
                0
                5px
                22px
                rgba(15, 23, 42, 0.07);
        }

        [data-testid="stChatInput"] textarea {

            font-size: 15px;
        }


        /* =================================================
           BUTTONS
        ================================================= */

        .stButton button {

            border-radius: 9px;

            font-weight: 500;
        }

        .stLinkButton a {

            display: flex;

            align-items: center;
            justify-content: center;

            border-radius: 9px;

            font-weight: 600;
        }


        /* =================================================
           OPERATIONAL SECTION
        ================================================= */

        .operational-label {

            margin-bottom: 3px;

            font-size: 12px;

            font-weight: 650;

            letter-spacing: 0.055em;

            color: #94a3b8;

            text-transform: uppercase;
        }


        /* =================================================
           BORDER CONTAINERS
        ================================================= */

        [data-testid="stVerticalBlockBorderWrapper"] {

            border-radius: 12px;

            background: #ffffff;
        }


        /* =================================================
           METRICS
        ================================================= */

        [data-testid="stMetric"] {

            padding-top: 0;
            padding-bottom: 0;
        }

        [data-testid="stMetricLabel"] {

            font-size: 12px;

            color: #64748b;
        }

        [data-testid="stMetricValue"] {

            font-weight: 650;
        }


        /* =================================================
           EXPANDERS
        ================================================= */

        [data-testid="stExpander"] {

            background: #ffffff;

            border:
                1px solid
                rgba(15, 23, 42, 0.075);

            border-radius: 10px;
        }

        [data-testid="stExpander"] summary {

            font-size: 14px;

            font-weight: 500;
        }


        /* =================================================
           LINKS
        ================================================= */

        a {

            text-decoration-thickness: 1px;

            text-underline-offset: 3px;
        }


        /* =================================================
           DIVIDERS
        ================================================= */

        hr {

            margin-top: 1.6rem !important;

            margin-bottom: 1.6rem !important;

            border-color:
                rgba(15, 23, 42, 0.075) !important;
        }


        /* =================================================
           SUCCESS / INFO
        ================================================= */

        [data-testid="stAlert"] {

            border-radius: 10px;
        }


        /* =================================================
           MOBILE
        ================================================= */

        @media (max-width: 760px) {

            .block-container {

                padding-left: 1rem;
                padding-right: 1rem;
            }

            .copilot-title {

                font-size: 22px;
            }

            .copilot-subtitle {

                margin-left: 0;

                margin-top: 10px;
            }

            [data-testid="stChatMessage"]:has(
                .chat-assistant-marker
            )
            [data-testid="stChatMessageContent"] {

                max-width: 100%;
            }

            [data-testid="stChatMessage"]:has(
                .chat-user-marker
            )
            [data-testid="stChatMessageContent"] {

                max-width: 84%;
            }
        }

        </style>
        """
    )