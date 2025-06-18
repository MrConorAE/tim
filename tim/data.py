import datetime
import sqlite3 as sql

import typer
from typing_extensions import List, Literal, Optional, Tuple

from . import helpers as h

conn = None


class Transaction:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        self.cur = self._conn.cursor()
        h.vprint("data:    transaction: start")
        return self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
            h.vprint("data:    transaction: success")
            self.cur.close()
        else:
            self._conn.rollback()
            h.vprint("data:    transaction: fail")
            self.cur.close()
            h.print_error(
                f"failed to interact with database!\nerror: {exc_val}\nplease check the database exists and is accessible",
                "database error",
            )
            raise typer.Exit(code=3)


def init(path: str):
    global conn
    """Initialize the database."""
    h.vprint(f"data: connecting to database at {path}")
    h.create_db_directory(path)
    conn = sql.connect(path)
    with Transaction(conn) as t:
        t.execute(
            "CREATE TABLE IF NOT EXISTS work (id INTEGER PRIMARY KEY AUTOINCREMENT, tags TEXT, start TIMESTAMP NOT NULL, end TIMESTAMP, bill TEXT, amended TEXT);"
        )


def start_work(tags: Optional[str]):
    """Start a new work item."""
    h.vprint("data: creating work log")
    with Transaction(conn) as t:
        t.execute(
            "INSERT INTO work VALUES (NULL,?,unixepoch(),NULL,NULL,NULL);", (tags,)
        )


def stop_work():
    """Stop the current work item."""
    h.vprint("data: stopping work log")
    with Transaction(conn) as t:
        t.execute("UPDATE work SET end = unixepoch() WHERE end IS NULL;")


def check_if_working() -> bool:
    """Return True if there is a currently open work session."""
    h.vprint("data: checking if currently working")
    with Transaction(conn) as t:
        return (
            t.execute("SELECT COUNT(*) FROM work WHERE end IS NULL;").fetchone()[0] != 0
        )


def get_current_tracking() -> Tuple[int, int, str]:
    """Return current tracking details."""
    h.vprint("data: getting current work")
    with Transaction(conn) as t:
        return t.execute(
            "SELECT start, unixepoch()-start, tags FROM work WHERE end IS NULL;"
        ).fetchone()


def get_last_tracking() -> Tuple[int, int, int, str, str]:
    """Return the last tracking details."""
    h.vprint("data: getting last work")
    with Transaction(conn) as t:
        return t.execute(
            "SELECT start, end, end-start, tags, bill FROM work ORDER BY end DESC LIMIT 1;"
        ).fetchone()

def get_tracking(id: int) -> Tuple[int, int, int, str, str]:
    """Return a specific tracking details."""
    h.vprint(f"data: getting work id {id}")
    with Transaction(conn) as t:
        return t.execute(
            "SELECT start, end, end-start, tags, bill FROM work WHERE id = ?;", (id, )
        ).fetchone()


def get_work_log(
    range: h.Range, billed: bool | None, filter: List[str] | None, partial: bool
) -> List[Tuple[int, int, int, int, str, str, str]]:
    """Return a list of tracked work in range."""
    h.vprint(f"data: getting work log for {range.value}")
    with Transaction(conn) as t:
        if range == h.Range.today:
            span = "WHERE start > unixepoch('now','localtime','start of day') "
        elif range == h.Range.week:
            span = (
                "WHERE start > unixepoch('now','localtime','start of day','-7 days') "
            )
        elif range == h.Range.month:
            span = "WHERE start > unixepoch('now','localtime','start of day','-1 month', 'floor') "
        elif range == h.Range.year:
            span = "WHERE start > unixepoch('now','localtime','start of day','-1 year', 'floor') "
        else:
            span = "WHERE start IS NOT NULL "

        if billed is not None:
            if billed is True:
                span += "AND bill IS NOT NULL "
            else:
                span += "AND bill IS NULL "

        filter_terms = []
        if filter is not None:
            if partial:
                for term in filter:
                    span += "AND (tags LIKE ?) "
                    filter_terms.append(f"%{term}%")
            else:
                for term in filter:
                    span += "AND ("
                    span += "tags LIKE ? or "
                    filter_terms.append(f"{term} %")  # start of string
                    span += "tags LIKE ? or "
                    filter_terms.append(f"% {term} %")  # middle
                    span += "tags LIKE ? or "
                    filter_terms.append(f"% {term}")  # end
                    span += "tags = ?) "
                    filter_terms.append(f"{term}")  # whole

        h.vprint(f"data: work log filter is '{span}'")
        return t.execute(
            f"SELECT id, start, end, end-start, tags, bill, amended FROM work {span}ORDER BY start ASC;",
            filter_terms or tuple(),
        ).fetchall()


def test_id_exists(id: int) -> int|None:
    """Check the given ID exists in the database."""
    h.vprint(f"data: testing if id {id} exists")
    with Transaction(conn) as t:
        if id == 0:
            id = t.execute("SELECT id FROM work ORDER BY end DESC LIMIT 1;").fetchone()[
                0
            ]

        # check it exists
        exists = t.execute("SELECT COUNT(*) FROM work WHERE id = ?;", (id,)).fetchone()[
            0
        ]
        if exists != 0:
            h.vprint("data:  record exists")
            return id
        else:
            h.vprint("data:  record does not exist")
            return None

def delete_work(id: int) -> bool:
    """Delete a row from the table."""
    h.vprint(f"data: deleting work log for id {id}")
    with Transaction(conn) as t:
        result = test_id_exists(id)
        if result is not None:
            h.vprint("data:  record exists")
            t.execute("DELETE FROM work WHERE id = ?;", (result,))
            return True
        else:
            h.vprint("data:  record does not exist")
            return False


def mark_work_billed(
    range_from: datetime.datetime | None,
    range_to: datetime.datetime | None,
    range_all: bool,
    filter: List[str] | None,
    partial: bool,
    ref: str | None,
    unbill: bool,
) -> None:
    """Mark work in range and matching filter as billed (or not)."""
    h.vprint(
        f"data: marking work from {range_from} to {range_to} (all {range_all}) with tags {filter} (partial {partial}) as {"not " if unbill else ""}billed with ref {ref}"
    )

    with Transaction(conn) as t:
        substs = []
        span = ""

        if range_all:
            span += "WHERE start IS NOT NULL "
        else:
            if range_from and range_to:
                from_ts = range_from.timestamp()
                to_ts = range_to.timestamp()
                span += "WHERE start >= ? AND end <= ? "
                substs.append(int(from_ts))
                substs.append(int(to_ts))
            elif range_from:
                from_ts = range_from.timestamp()
                span += "WHERE start >= ? "
                substs.append(int(from_ts))
            elif range_to:
                to_ts = range_to.timestamp()
                span += "WHERE end <= ? "
                substs.append(int(to_ts))

        filter_terms = []
        if filter is not None:
            if partial:
                for term in filter:
                    span += "AND (tags LIKE ?) "
                    filter_terms.append(f"%{term}%")
            else:
                for term in filter:
                    span += "AND ("
                    span += "tags LIKE ? or "
                    filter_terms.append(f"{term} %")  # start of string
                    span += "tags LIKE ? or "
                    filter_terms.append(f"% {term} %")  # middle
                    span += "tags LIKE ? or "
                    filter_terms.append(f"% {term}")  # end
                    span += "tags = ?) "
                    filter_terms.append(f"{term}")  # whole
            substs += filter_terms

        if not unbill:
            substs.insert(0, ref or "yes")

        h.vprint(f"data: bill work filter is '{span}'")
        h.vprint(f"data: substs are {substs}")

        if unbill:
            t.execute(f"UPDATE work SET bill = NULL {span};", substs)
        else:
            t.execute(f"UPDATE work SET bill = ? {span};", substs)


def amend_tags(id: int, tags: Optional[str]):
    """Change tags of an item."""
    h.vprint("data: amending tags")
    with Transaction(conn) as t:
        t.execute("UPDATE work SET tags = ? WHERE id = ?;", (tags, id))


def amend_time(id: int, which: Literal['start','end'], time: datetime.datetime):
    """Change timestamps of an item."""
    h.vprint("data: amending timestamp")
    with Transaction(conn) as t:
        if which == 'start':
            t.execute("UPDATE work SET start = ?, amended = 'yes' WHERE id = ?;", (int(time.timestamp()), id))
        elif which == 'end':
            t.execute("UPDATE work SET end = ?, amended = 'yes' WHERE id = ?;", (int(time.timestamp()), id))
