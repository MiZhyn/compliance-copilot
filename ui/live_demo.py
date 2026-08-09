# ui/live_demo.py

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.orchestration.travel_copilot import (
    FST_BOOKING_URL,
    TravelCopilotResponse,
)

from ui.resources import (
    get_travel_copilot,
)

from ui.styles import (
    render_html,
)


# =========================================================
# Avatars (Material vector icons — crisp at small sizes)
# =========================================================

USER_AVATAR = ":material/person:"
ASSISTANT_AVATAR = ":material/flight_takeoff:"


# =========================================================
# Example queries
# =========================================================

EXAMPLE_TRAVEL_QUERY = """
I'm an Indian passport holder.
I arrive on SQ12 on Aug 20
and depart on SQ318 on Aug 20.
Which Free Singapore Tours can I join,
and do I need a visa?
""".strip()


EXAMPLE_CUSTOMS_QUERY = (
    "Can I bring a drone into Singapore?"
)


EXAMPLE_FST_QUERY = (
    "Give me more detail about City Sights Tour."
)


# =========================================================
# Session state
# =========================================================

def _init_session_state() -> None:

    if "messages" not in st.session_state:

        st.session_state["messages"] = []


    # Backward-compatible migration from the old global
    # last_result design. Structured output now belongs to
    # the assistant turn that produced it.
    legacy_result = st.session_state.pop(
        "last_result",
        None,
    )

    if legacy_result is not None:

        for message in reversed(
            st.session_state["messages"]
        ):

            if (
                message.get("role") == "assistant"
                and "result" not in message
            ):

                message["result"] = legacy_result
                break


# =========================================================
# Conversation context
# =========================================================

def _build_conversation_context() -> str | None:
    """
    Build short-term conversational context.

    Current query is not included here.
    """

    messages = st.session_state.get("messages", [])

    if not messages:

        return None

    # Around 3 recent turns.
    recent_messages = messages[-6:]

    lines: list[str] = []

    for message in recent_messages:

        role = message.get("role", "unknown")
        content = message.get("content", "")

        structured_context = message.get(
            "structured_context",
            "",
        )

        if structured_context:

            content = (
                f"{content}\n\n"
                "[Structured operational result]\n"
                f"{structured_context}"
            )

        lines.append(
            f"{role.upper()}:\n{content}"
        )

    context = "\n\n".join(lines)

    return context[-6000:]


# =========================================================
# Chat message
#
# Bubble + (for the assistant) its structured panels are
# rendered inside the same st.chat_message block, so the
# reply text and the Journey / FST panels share one column.
# =========================================================

def _render_chat_message(
    role: str,
    content: str,
    result: TravelCopilotResponse | None = None,
) -> None:

    if role == "user":

        avatar = USER_AVATAR
        marker = "chat-user-marker"

    else:

        avatar = ASSISTANT_AVATAR
        marker = "chat-assistant-marker"

    with st.chat_message(role, avatar=avatar):

        # Invisible CSS marker
        st.html(
            f'<span class="{marker}"></span>'
        )

        st.markdown(content)

        if (
            role == "assistant"
            and result is not None
        ):

            _render_operational_result(result)
            _render_details(result)


# =========================================================
# Datetime helpers
# =========================================================

def _effective_datetime(
    flight: dict,
) -> str | None:

    return (
        flight.get("estimated_datetime")
        or flight.get("scheduled_datetime")
    )


def _parse_datetime(
    value: str,
) -> datetime:

    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S",
    )


def _format_datetime(
    value: str | None,
) -> str:

    if not value:

        return "-"

    parsed = _parse_datetime(value)

    return (
        parsed.strftime("%d %b %Y · %H:%M")
        .lstrip("0")
    )


def _format_date(
    value: str,
) -> str:

    parsed = _parse_datetime(value)

    return (
        parsed.strftime("%d %b %Y")
        .lstrip("0")
    )


def _format_time(
    value: str,
) -> str:

    parsed = _parse_datetime(value)

    return parsed.strftime("%H:%M")


def _format_terminal(
    value,
) -> str:

    if not value:

        return "-"

    value = str(value)

    if value.upper().startswith("T"):

        return value.upper()

    return f"T{value}"


def _format_transit(
    hours: float,
) -> str:

    whole_hours = int(hours)

    minutes = round(
        (hours - whole_hours) * 60
    )

    if minutes == 60:

        whole_hours += 1
        minutes = 0

    return f"{whole_hours}h {minutes:02d}m"


# =========================================================
# Journey
# =========================================================

def _render_journey(
    result: TravelCopilotResponse,
) -> None:

    if not result.flight_facts:

        return

    arrival = result.flight_facts.get("arrival")
    departure = result.flight_facts.get("departure")

    st.markdown("### ✈️ Your Journey")

    with st.container(border=True):

        (
            arrival_col,
            transit_col,
            departure_col,
        ) = st.columns(
            [1.4, 1, 1.4],
            vertical_alignment="center",
        )

        # =================================================
        # Arrival
        # =================================================

        with arrival_col:

            render_html(
                """
                <div class="operational-label">
                    Arrival
                </div>
                """
            )

            if arrival:

                st.markdown(
                    "### "
                    f"{arrival.get('flight_number', '-')}"
                )

                st.write(
                    _format_datetime(
                        _effective_datetime(arrival)
                    )
                )

                st.caption(
                    _format_terminal(
                        arrival.get("terminal")
                    )
                )

        # =================================================
        # Transit
        # =================================================

        with transit_col:

            render_html(
                """
                <div class="operational-label">
                    Transit
                </div>
                """
            )

            if result.transit_hours is not None:

                st.markdown(
                    "### "
                    f"{_format_transit(result.transit_hours)}"
                )

                st.caption("Layover")

        # =================================================
        # Departure
        # =================================================

        with departure_col:

            render_html(
                """
                <div class="operational-label">
                    Departure
                </div>
                """
            )

            if departure:

                st.markdown(
                    "### "
                    f"{departure.get('flight_number', '-')}"
                )

                st.write(
                    _format_datetime(
                        _effective_datetime(departure)
                    )
                )

                st.caption(
                    _format_terminal(
                        departure.get("terminal")
                    )
                )


# =========================================================
# FST sessions
# =========================================================

def _render_fst_sessions(
    result: TravelCopilotResponse,
) -> None:

    if result.fst_result is None:

        return

    sessions = result.fst_result.eligible_sessions

    st.markdown(
        "### 🚌 Available Free Singapore Tours"
    )

    st.caption(
        "Based on your flight timing and "
        "the demo operational availability."
    )

    if not sessions:

        st.warning(
            "No tour session is operationally "
            "feasible for this journey."
        )

        return

    st.success(
        f"{len(sessions)} sessions fit your journey."
    )

    for session in sessions:

        with st.container(border=True):

            (
                tour_col,
                date_col,
                time_col,
                availability_col,
                action_col,
            ) = st.columns(
                [2.5, 1.15, 1.35, 1.15, 1.05],
                vertical_alignment="center",
            )

            # =================================================
            # Tour
            # =================================================

            with tour_col:

                st.markdown(
                    f"**{session.tour_name}**"
                )

                st.caption("Free Singapore Tour")

            # =================================================
            # Date
            # =================================================

            with date_col:

                render_html(
                    """
                    <div class="operational-label">
                        Date
                    </div>
                    """
                )

                st.write(
                    _format_date(session.start_datetime)
                )

            # =================================================
            # Time
            # =================================================

            with time_col:

                render_html(
                    """
                    <div class="operational-label">
                        Time
                    </div>
                    """
                )

                start_time = _format_time(
                    session.start_datetime
                )

                end_time = _format_time(
                    session.end_datetime
                )

                st.write(
                    f"{start_time} – {end_time}"
                )

            # =================================================
            # Availability
            # =================================================

            with availability_col:

                render_html(
                    """
                    <div class="operational-label">
                        Availability
                    </div>
                    """
                )

                slots = session.remaining_slots

                if slots <= 3:

                    st.markdown(
                        f"**{slots} slots left**"
                    )

                else:

                    st.write(
                        f"{slots} slots left"
                    )

            # =================================================
            # Booking
            # =================================================

            with action_col:

                render_html(
                    """
                    <div class="operational-label">
                        Action
                    </div>
                    """
                )

                if session.remaining_slots > 0:

                    st.link_button(
                        "Book now ↗",
                        FST_BOOKING_URL,
                        use_container_width=True,
                    )


# =========================================================
# Operational result
# =========================================================

def _render_operational_result(
    result: TravelCopilotResponse,
) -> None:

    has_result = (
        bool(result.flight_facts)
        or (result.transit_hours is not None)
        or (result.fst_result is not None)
    )

    if not has_result:

        return

    st.divider()

    _render_journey(result)

    if result.fst_result is not None:

        st.write("")

        _render_fst_sessions(result)


# =========================================================
# Trace
# =========================================================

def _render_trace(
    result: TravelCopilotResponse,
) -> None:

    with st.expander(
        "How did the copilot answer this?",
        expanded=False,
    ):

        # =================================================
        # Planner
        # =================================================

        st.markdown("#### Planner")

        st.caption(
            "Intent understanding, entity extraction "
            "and query decomposition."
        )

        st.json(result.request.model_dump())

        # =================================================
        # Operational
        # =================================================

        st.markdown("#### Operational tools")

        executed = False

        if result.flight_facts:

            st.write("✓ Flight database lookup")
            executed = True

        if result.transit_hours is not None:

            st.write(
                "✓ Deterministic transit calculation"
            )
            executed = True

        if result.fst_result is not None:

            st.write(
                "✓ FST availability and feasibility check"
            )
            executed = True

        if not executed:

            st.caption(
                "No SQL / Python tool was required."
            )

        # =================================================
        # Retrieval
        # =================================================

        st.markdown("#### Knowledge retrieval")

        if not result.knowledge_results:

            st.caption(
                "No RAG retrieval was required."
            )

        else:

            for group in result.knowledge_results:

                st.markdown(
                    f"**{group.topic.upper()}**"
                )

                st.caption(group.query)

                for evidence in group.evidence[:3]:

                    st.write(
                        "✓ "
                        f"{evidence.document.title}"
                        " · score "
                        f"{evidence.rerank_score}"
                    )

        # =================================================
        # Synthesis
        # =================================================

        st.markdown("#### Final synthesis")

        st.caption(
            "Claude combined retrieved policy evidence "
            "with deterministic operational results."
        )


# =========================================================
# Evidence
# =========================================================

def _render_evidence(
    result: TravelCopilotResponse,
) -> None:

    if not result.knowledge_results:

        return

    with st.expander(
        "Retrieved Evidence",
        expanded=False,
    ):

        for group in result.knowledge_results:

            st.markdown(
                f"### {group.topic.upper()}"
            )

            st.caption(
                f"Focused query: {group.query}"
            )

            for index, evidence in enumerate(
                group.evidence,
                start=1,
            ):

                document = evidence.document

                st.markdown(
                    f"**{index}. {document.title}**"
                )

                st.caption(
                    f"{document.source}"
                    " · rerank "
                    f"{evidence.rerank_score}"
                )

                if document.heading_path:

                    st.caption(document.heading_path)

                st.write(document.content)

                if document.url:

                    st.markdown(
                        "[Open official source ↗]"
                        f"({document.url})"
                    )

                st.divider()


# =========================================================
# Details
# =========================================================

def _render_details(
    result: TravelCopilotResponse,
) -> None:

    st.write("")

    _render_trace(result)

    _render_evidence(result)


# =========================================================
# Structured context for follow-up questions
# =========================================================

def _build_structured_context(
    result: TravelCopilotResponse,
) -> str:

    lines: list[str] = []

    if result.flight_facts:

        arrival = result.flight_facts.get("arrival")
        departure = result.flight_facts.get("departure")

        if arrival:
            lines.append(
                "Arrival: "
                f"{arrival.get('flight_number', '-')} | "
                f"{_effective_datetime(arrival) or '-'} | "
                f"{_format_terminal(arrival.get('terminal'))}"
            )

        if departure:
            lines.append(
                "Departure: "
                f"{departure.get('flight_number', '-')} | "
                f"{_effective_datetime(departure) or '-'} | "
                f"{_format_terminal(departure.get('terminal'))}"
            )

    if result.transit_hours is not None:
        lines.append(
            "Transit: "
            f"{_format_transit(result.transit_hours)}"
        )

    if result.fst_result is not None:

        sessions = result.fst_result.eligible_sessions

        if sessions:
            lines.append("Eligible FST sessions:")

            for index, session in enumerate(
                sessions,
                start=1,
            ):

                lines.append(
                    f"{index}. {session.tour_name} | "
                    f"{session.start_datetime} - "
                    f"{session.end_datetime} | "
                    f"{session.remaining_slots} slots left"
                )

        else:
            lines.append("Eligible FST sessions: none")

    return "\n".join(lines)


# =========================================================
# Run query
# =========================================================

def _run_query(
    query: str,
) -> None:
    """
    UX sequence:

    1. show user message immediately
    2. planner / RAG / SQL / Python
    3. stream Claude synthesis
    4. render structured operational result (inside the
       same assistant block, so it aligns with the reply)
    """

    # =====================================================
    # Previous conversation context
    # =====================================================

    conversation_context = _build_conversation_context()

    # =====================================================
    # Store + show USER immediately
    # =====================================================

    st.session_state["messages"].append(
        {
            "role": "user",
            "content": query,
        }
    )

    _render_chat_message(
        role="user",
        content=query,
    )

    # =====================================================
    # Cached backend
    # =====================================================

    copilot = get_travel_copilot()

    # =====================================================
    # Assistant (reply + panels share one block)
    # =====================================================

    with st.chat_message(
        "assistant",
        avatar=ASSISTANT_AVATAR,
    ):

        st.html(
            '<span class="chat-assistant-marker"></span>'
        )

        # =================================================
        # Planner + DB + Python + RAG
        # =================================================

        loading = st.empty()

        with loading:

            with st.spinner(
                "Checking policies and operational data..."
            ):

                prepared = copilot.prepare(
                    user_query=query,
                    conversation_context=conversation_context,
                )

        loading.empty()

        # =================================================
        # Direct response
        # =================================================

        if prepared.direct_answer:

            answer = prepared.direct_answer

            st.markdown(answer)

        # =================================================
        # Streaming synthesis
        # =================================================

        else:

            answer = st.write_stream(
                copilot.stream_answer(prepared),
                cursor="▌",
            )

        # =================================================
        # Structured output — rendered INSIDE the block so
        # it lines up under the reply, not full-page width.
        # =================================================

        result = copilot.build_response(
            prepared=prepared,
            answer=answer,
        )

        _render_operational_result(result)
        _render_details(result)

    # =====================================================
    # Save answer + its result on the message
    # =====================================================

    st.session_state["messages"].append(
        {
            "role": "assistant",
            "content": answer,
            "result": result,
            "structured_context": _build_structured_context(
                result
            ),
        }
    )


# =========================================================
# Page
# =========================================================

def render_live_demo() -> None:

    _init_session_state()

    # =====================================================
    # Header
    # =====================================================

    render_html(
        """
        <div class="copilot-header">

            <div class="copilot-brand">

                <div class="copilot-logo">
                    ✈️
                </div>

                <div class="copilot-title">
                    Travel & Compliance Copilot
                </div>

            </div>

            <div class="copilot-subtitle">
                Ask about Singapore visa requirements,
                customs rules, transit, or Free Singapore Tour.
            </div>

        </div>
        """
    )

    # =====================================================
    # Quick prompts + clear
    # =====================================================

    render_html(
        """
        <div class="quick-label">
            Try an example
        </div>
        """
    )

    (
        example_col_1,
        example_col_2,
        example_col_3,
        clear_col,
    ) = st.columns(
        [1.5, 1.2, 1.5, 0.8]
    )

    pending_query = None

    with example_col_1:

        with st.popover(
            "✈️ Visa + FST",
            use_container_width=True,
        ):

            st.caption("EXAMPLE QUESTION")

            st.write(EXAMPLE_TRAVEL_QUERY)

            if st.button(
                "Use this question →",
                key="use_example_travel",
                type="primary",
                use_container_width=True,
            ):

                pending_query = EXAMPLE_TRAVEL_QUERY

    with example_col_2:

        with st.popover(
            "🛃 Bring a drone",
            use_container_width=True,
        ):

            st.caption("EXAMPLE QUESTION")

            st.write(EXAMPLE_CUSTOMS_QUERY)

            if st.button(
                "Use this question →",
                key="use_example_customs",
                type="primary",
                use_container_width=True,
            ):

                pending_query = EXAMPLE_CUSTOMS_QUERY

    with example_col_3:

        with st.popover(
            "🚌 City Sights Tour",
            use_container_width=True,
        ):

            st.caption("EXAMPLE QUESTION")

            st.write(EXAMPLE_FST_QUERY)

            if st.button(
                "Use this question →",
                key="use_example_fst",
                type="primary",
                use_container_width=True,
            ):

                pending_query = EXAMPLE_FST_QUERY

    with clear_col:

        if st.button(
            "Clear",
            use_container_width=True,
        ):

            st.session_state["messages"] = []

            st.rerun()

    st.write("")

    # =====================================================
    # Existing conversation
    # =====================================================

    for message in st.session_state["messages"]:

        _render_chat_message(
            role=message["role"],
            content=message["content"],
            result=message.get("result"),
        )

    # =====================================================
    # Chat input
    # =====================================================

    prompt = st.chat_input(
        "Ask about visa, customs, transit or FST...",
    )

    if prompt:

        pending_query = prompt

    # =====================================================
    # New query
    # =====================================================

    if pending_query:

        _run_query(pending_query)