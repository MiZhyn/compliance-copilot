# ui/styles.py

from __future__ import annotations

from textwrap import dedent

import streamlit as st


# =========================================================
# HTML helper
# =========================================================

def render_html(content: str) -> None:
    """
    Render custom HTML without Markdown interpreting
    multiline indentation as code.
    """

    st.html(
        dedent(content).strip()
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

        html,
        body,
        [data-testid="stAppViewContainer"],
        .stApp {
            background: #f8f9fb;
        }


        /*
        Main conversation/content column.

        Important:
        Keep this width consistent with CHAT_CONTENT_WIDTH
        used in the Python st.bottom section.
        */
        .block-container {
            max-width: 1050px;

            padding-top: 2.2rem;
            padding-bottom: 8rem;

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

            color: #272b38;
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
           CHAT MESSAGE — BASE
        ================================================= */

        [data-testid="stChatMessage"] {

            background: transparent;

            border: none;

            gap: 0.55rem;

            /*
            Keep message spacing controlled here rather than
            through large child margins.
            */
            padding-top: 0.35rem;
            padding-bottom: 0.65rem;

            align-items: flex-start;
        }


        [data-testid="stChatMessageContent"] {

            line-height: 1.60;

            font-size: 15px;

            min-width: 0;
        }


        /* =================================================
           REMOVE MARKER WRAPPER SPACE
        ================================================= */

        /*
        IMPORTANT:

        display:none on .chat-user-marker itself is not enough.

        Streamlit creates an ElementContainer around the
        marker. That wrapper can still participate in the
        vertical layout and create the mysterious empty space
        inside/above the message.

        We therefore remove the entire Streamlit wrapper.
        */

        [data-testid="stChatMessage"]
        [data-testid="stElementContainer"]:has(
            .chat-user-marker
        ) {
            display: none !important;
        }


        [data-testid="stChatMessage"]
        [data-testid="stElementContainer"]:has(
            .chat-assistant-marker
        ) {
            display: none !important;
        }


        /*
        Marker itself is also hidden as a fallback.
        */

        .chat-user-marker,
        .chat-assistant-marker {
            display: none !important;
        }


        /* =================================================
           ASSISTANT MESSAGE
        ================================================= */

        /*
        Assistant uses full available width.

        The avatar stays on the left and the answer occupies
        the remaining horizontal space.
        */

        [data-testid="stChatMessage"]:has(
            .chat-assistant-marker
        ) {
            flex-direction: row;

            justify-content: flex-start;

            align-items: flex-start;
        }


        [data-testid="stChatMessage"]:has(
            .chat-assistant-marker
        )
        [data-testid="stChatMessageContent"] {

            flex: 1 1 auto;

            width: 100%;

            min-width: 0;

            max-width: none;

            padding:
                2px
                0;

            background: transparent;

            border: none;

            border-radius: 0;

            box-shadow: none;
        }


        /* =================================================
           USER MESSAGE
        ================================================= */

        /*
        Keep the user's avatar and bubble as one compact group
        aligned to the right side of the chat row.
        */

        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        ) {
            display: flex !important;

            flex-direction: row-reverse !important;

            justify-content: flex-start !important;

            align-items: flex-start !important;

            gap: 0.55rem !important;

            padding-top: 0.25rem;

            padding-bottom: 0.45rem;

            min-height: 0 !important;
        }


        /*
        Prevent Streamlit's content wrapper from stretching
        across the row. The bubble should hug its text while
        still wrapping when the message becomes long.
        */

        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        )
        [data-testid="stChatMessageContent"] {

            flex:
                0
                1
                auto !important;

            width: fit-content !important;

            max-width: 74% !important;

            min-width: 0;

            margin: 0 !important;

            padding:
                11px
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

            box-sizing: border-box;

            line-height: 1.55;

            overflow-wrap: anywhere;
        }


        /*
        Keep the avatar compact and remove any accidental
        auto-margin that could separate it from the bubble.
        */

        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        )
        [data-testid="stChatMessageAvatar"] {

            flex:
                0
                0
                auto !important;

            margin: 0 !important;
        }


        /*
        Inner Streamlit wrappers follow the bubble width.
        */

        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        )
        [data-testid="stChatMessageContent"] > div {

            width: auto !important;

            max-width: 100%;

            margin: 0 !important;

            padding: 0 !important;
        }


        /*
        Remove Markdown paragraph spacing inside the user bubble.
        */

        [data-testid="stChatMessage"]:has(
            .chat-user-marker
        )
        [data-testid="stChatMessageContent"] p {

            margin: 0 !important;

            padding: 0 !important;
        }


        /* =================================================
           GENERAL CHAT MARKDOWN
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


        [data-testid="stChatMessageContent"] h1 {
            letter-spacing: -0.025em;
        }


        [data-testid="stChatMessageContent"] h2 {
            letter-spacing: -0.02em;
        }


        [data-testid="stChatMessageContent"] h3 {

            font-size: 16px;
        }


        [data-testid="stChatMessageContent"] ul {

            margin-top: 0.35rem;

            margin-bottom: 0.45rem;
        }


        [data-testid="stChatMessageContent"] ol {

            margin-top: 0.35rem;

            margin-bottom: 0.45rem;
        }

        /* =================================================
        BOTTOM CHAT AREA
        ================================================= */

        /*
        The bottom region itself remains full-screen because
        Streamlit owns this layer.

        We make it visually neutral.
        */

        [data-testid="stBottom"] {
            background: rgba(248, 249, 251, 0.97);

            border-top: none;

            box-shadow:
                0 -8px 24px
                rgba(248, 249, 251, 0.96);
        }


        /*
        Important:

        st.bottom uses its own internal width, completely
        independent from .block-container.

        Force the inner bottom layout to use the same
        1050px centered grid as the main page.
        */

        [data-testid="stBottom"] > div {
            width: 100% !important;
        }


        /*
        Our keyed Streamlit container.
        */

        .st-key-chat_input_shell {
            width: calc(100% - 4rem) !important;

            max-width: 1050px !important;

            margin-left: auto !important;
            margin-right: auto !important;

            padding:
                0.55rem
                0
                0.75rem
                0 !important;

            box-sizing: border-box;
        }


        /* =================================================
        CHAT INPUT
        ================================================= */

        .st-key-chat_input_shell
        [data-testid="stChatInput"] {

            width: 100% !important;

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

            overflow: hidden;
        }


        .st-key-chat_input_shell
        [data-testid="stChatInput"] textarea {

            font-size: 15px;

            line-height: 1.45;

            padding-top: 12px;

            padding-bottom: 12px;
        }
 

        /* =================================================
           BUTTONS
        ================================================= */

        .stButton button {

            border-radius: 9px;

            font-weight: 500;

            min-height: 42px;
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

            overflow: hidden;
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
                rgba(15, 23, 42, 0.075)
                !important;
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

                padding-top: 1.25rem;

                padding-bottom: 7rem;
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

                width: 100%;

                max-width: 100%;
            }


            [data-testid="stChatMessage"]:has(
                .chat-user-marker
            )
            [data-testid="stChatMessageContent"] {

                max-width: 86%;

                padding:
                    11px
                    14px;
            }


            .st-key-chat_input_shell {

                width: calc(100% - 2rem) !important;

                padding:
                    0.4rem
                    0
                    0.55rem
                    0 !important;
            }


            [data-testid="stChatInput"] {

                border-radius: 14px;
            }
        }

        </style>
        """
    )