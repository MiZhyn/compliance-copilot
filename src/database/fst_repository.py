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


class FSTRepository:
    """
    Read Free Singapore Tour operational session data.

    This layer only retrieves session facts.
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


    def get_sessions_by_date(
        self,
        service_date: str,
    ) -> list[dict]:
        """
        Get all FST sessions operating on one date.
        """

        sql = """
        SELECT
            id,
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
        FROM fst_sessions
        WHERE service_date = ?
        ORDER BY start_datetime
        """

        with self._connect() as connection:

            rows = connection.execute(
                sql,
                (service_date,),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


    def get_session(
        self,
        session_code: str,
    ) -> dict | None:

        sql = """
        SELECT
            id,
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
        FROM fst_sessions
        WHERE session_code = ?
        LIMIT 1
        """

        with self._connect() as connection:

            row = connection.execute(
                sql,
                (session_code,),
            ).fetchone()

        if row is None:

            return None

        return dict(row)