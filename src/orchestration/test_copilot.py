from src.orchestration.travel_copilot import (
    TravelCopilot,
)


def main() -> None:

    query = """
I'm an Indian passport holder.

I arrive on SQ12 on Aug 20
and depart on SQ318 on Aug 20.

Which Free Singapore Tours can I join,
and do I need a visa?
""".strip()

    copilot = TravelCopilot()

    result = copilot.run(
        query
    )

    print(
        "\n===================================="
    )

    print(
        "FINAL ANSWER"
    )

    print(
        "===================================="
    )

    print(
        result.answer
    )


if __name__ == "__main__":
    main()