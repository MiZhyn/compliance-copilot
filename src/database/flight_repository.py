from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "database"
    / "flights_fst.db"
)


class FlightRepository:
    """
    Read operational flight facts from SQLite.

    This layer does NOT contain business logic.
    It only retrieves data.
    """

    def __init__(
        self,
        db_path: Path = DB_PATH,
    ) -> None:

        self.db_path = db_path

        if not self.db_path.exists():

            raise FileNotFoundError(
                f"Database not found: "
                f"{self.db_path}"
            )


    def _connect(
        self,
    ) -> sqlite3.Connection:

        connection = sqlite3.connect(
            self.db_path
        )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection


    def get_flight(
        self,
        flight_number: str,
        flight_date: str,
        direction: str,
    ) -> dict | None:
        """
        Get one flight by:

        - flight number
        - date
        - direction

        direction:
            ARRIVAL
            DEPARTURE
        """

        sql = """
        SELECT
            id,
            flight_number,
            flight_date,
            direction,
            origin,
            destination,
            terminal,
            scheduled_datetime,
            estimated_datetime,
            status
        FROM flights
        WHERE
            UPPER(flight_number) = UPPER(?)
            AND flight_date = ?
            AND UPPER(direction) = UPPER(?)
        LIMIT 1
        """

        with self._connect() as connection:

            row = connection.execute(
                sql,
                (
                    flight_number,
                    flight_date,
                    direction,
                ),
            ).fetchone()

        if row is None:

            return None

        return dict(row)


    def get_all_flights(
        self,
    ) -> list[dict]:

        sql = """
        SELECT
            id,
            flight_number,
            flight_date,
            direction,
            origin,
            destination,
            terminal,
            scheduled_datetime,
            estimated_datetime,
            status
        FROM flights
        ORDER BY scheduled_datetime
        """

        with self._connect() as connection:

            rows = connection.execute(
                sql
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]