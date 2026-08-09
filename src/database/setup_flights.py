from __future__ import annotations

import sqlite3
from pathlib import Path


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

DB_DIR = (
    PROJECT_ROOT
    / "data"
    / "database"
)

DB_PATH = (
    DB_DIR
    / "flights_fst.db"
)

DB_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Flight mock data
# =========================================================

FLIGHTS = [
    # -----------------------------------------------------
    # Case A
    # Main demo case
    #
    # Transit:
    # 07:45 -> 21:00
    # 13h 15m
    #
    # Enough time for multiple FST sessions.
    # -----------------------------------------------------
    (
        "SQ12",
        "2026-08-20",
        "ARRIVAL",
        "NRT",
        "SIN",
        "T3",
        "2026-08-20 07:45:00",
        None,
        "SCHEDULED",
    ),
    (
        "SQ318",
        "2026-08-20",
        "DEPARTURE",
        "SIN",
        "LHR",
        "T3",
        "2026-08-20 21:00:00",
        None,
        "SCHEDULED",
    ),

    # -----------------------------------------------------
    # Case B
    # Too short
    #
    # 11:30 -> 15:30
    # 4 hours
    # -----------------------------------------------------
    (
        "TR101",
        "2026-08-20",
        "ARRIVAL",
        "BKK",
        "SIN",
        "T1",
        "2026-08-20 11:30:00",
        None,
        "SCHEDULED",
    ),
    (
        "TR201",
        "2026-08-20",
        "DEPARTURE",
        "SIN",
        "KUL",
        "T1",
        "2026-08-20 15:30:00",
        None,
        "SCHEDULED",
    ),

    # -----------------------------------------------------
    # Case C
    # Too long
    #
    # 09:00 on Aug 20
    # ->
    # 10:00 on Aug 21
    #
    # 25 hours
    # -----------------------------------------------------
    (
        "AI101",
        "2026-08-20",
        "ARRIVAL",
        "DEL",
        "SIN",
        "T2",
        "2026-08-20 09:00:00",
        None,
        "SCHEDULED",
    ),
    (
        "AI202",
        "2026-08-21",
        "DEPARTURE",
        "SIN",
        "BOM",
        "T2",
        "2026-08-21 10:00:00",
        None,
        "SCHEDULED",
    ),

    # -----------------------------------------------------
    # Case D
    # Exact lower boundary
    #
    # 06:00 -> 11:30
    # 5.5 hours
    # -----------------------------------------------------
    (
        "CX101",
        "2026-08-20",
        "ARRIVAL",
        "HKG",
        "SIN",
        "T4",
        "2026-08-20 06:00:00",
        None,
        "SCHEDULED",
    ),
    (
        "CX202",
        "2026-08-20",
        "DEPARTURE",
        "SIN",
        "HKG",
        "T4",
        "2026-08-20 11:30:00",
        None,
        "SCHEDULED",
    ),
]


# =========================================================
# FST session mock data
# =========================================================

FST_SESSIONS = [
    (
        "FST-20260820-01",
        "2026-08-20",
        "Heritage and Culture Tour",
        "2026-08-20 10:00:00",
        "2026-08-20 12:30:00",
        "2026-08-20 08:30:00",
        "2026-08-20 14:30:00",
        20,
        8,
        "OPEN",
    ),
    (
        "FST-20260820-02",
        "2026-08-20",
        "City Sights Tour",
        "2026-08-20 12:00:00",
        "2026-08-20 14:30:00",
        "2026-08-20 10:30:00",
        "2026-08-20 16:30:00",
        20,
        3,
        "OPEN",
    ),
    (
        "FST-20260820-03",
        "2026-08-20",
        "Singapore River and Marina Bay Sands Tour",
        "2026-08-20 13:00:00",
        "2026-08-20 15:30:00",
        "2026-08-20 11:30:00",
        "2026-08-20 17:30:00",
        20,
        0,
        "FULL",
    ),
    (
        "FST-20260820-04",
        "2026-08-20",
        "Sentosa Discovery Tour",
        "2026-08-20 15:00:00",
        "2026-08-20 17:30:00",
        "2026-08-20 13:30:00",
        "2026-08-20 19:30:00",
        20,
        5,
        "OPEN",
    ),
    (
        "FST-20260820-05",
        "2026-08-20",
        "Singapore River and Marina Bay Sands Tour",
        "2026-08-20 16:00:00",
        "2026-08-20 18:30:00",
        "2026-08-20 14:30:00",
        "2026-08-20 20:30:00",
        20,
        7,
        "OPEN",
    ),
    (
        "FST-20260820-06",
        "2026-08-20",
        "City Sights Tour",
        "2026-08-20 18:00:00",
        "2026-08-20 20:30:00",
        "2026-08-20 16:30:00",
        "2026-08-20 22:30:00",
        20,
        2,
        "OPEN",
    ),
    (
        "FST-20260820-07",
        "2026-08-20",
        "Sentosa Discovery Tour",
        "2026-08-20 19:00:00",
        "2026-08-20 21:30:00",
        "2026-08-20 17:30:00",
        "2026-08-20 23:30:00",
        20,
        6,
        "OPEN",
    ),
]


# =========================================================
# Setup database
# =========================================================

def create_database() -> None:

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    try:

        # =================================================
        # 1. Flights table
        # =================================================

        cursor.execute(
            """
            DROP TABLE IF EXISTS flights
            """
        )

        cursor.execute(
            """
            CREATE TABLE flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                flight_number TEXT NOT NULL,

                flight_date TEXT NOT NULL,

                direction TEXT NOT NULL,

                origin TEXT,

                destination TEXT,

                terminal TEXT,

                scheduled_datetime TEXT NOT NULL,

                estimated_datetime TEXT,

                status TEXT NOT NULL
            )
            """
        )

        cursor.executemany(
            """
            INSERT INTO flights (
                flight_number,
                flight_date,
                direction,
                origin,
                destination,
                terminal,
                scheduled_datetime,
                estimated_datetime,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            FLIGHTS,
        )

        # =================================================
        # 2. FST sessions table
        # =================================================

        cursor.execute(
            """
            DROP TABLE IF EXISTS fst_sessions
            """
        )

        cursor.execute(
            """
            CREATE TABLE fst_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                session_code TEXT NOT NULL UNIQUE,

                service_date TEXT NOT NULL,

                tour_name TEXT NOT NULL,

                start_datetime TEXT NOT NULL,

                end_datetime TEXT NOT NULL,

                reporting_deadline TEXT NOT NULL,

                required_departure_after TEXT NOT NULL,

                capacity INTEGER NOT NULL,

                remaining_slots INTEGER NOT NULL,

                status TEXT NOT NULL
            )
            """
        )

        cursor.executemany(
            """
            INSERT INTO fst_sessions (
                session_code,
                service_date,
                tour_name,
                start_datetime,
                end_datetime,
                reporting_deadline,
                required_departure_after,
                capacity,
                remaining_slots,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            FST_SESSIONS,
        )

        # =================================================
        # Save
        # =================================================

        connection.commit()

    finally:

        connection.close()

    # =====================================================
    # Summary
    # =====================================================

    print(
        f"Database created: {DB_PATH}"
    )

    print(
        f"Flights inserted: {len(FLIGHTS)}"
    )

    print(
        f"FST sessions inserted: {len(FST_SESSIONS)}"
    )


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    create_database()