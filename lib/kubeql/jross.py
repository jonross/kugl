# These are from my personal library and are under the MIT license

import collections as co
import sqlite3
import subprocess as sp
import sys
from typing import Union


def run(args: Union[str, list[str]], error_ok=False):
    """
    Invoke an external command, which may be a list or a string; in the latter case it will be
    interpreted using bash -c.  Returns exit status, stdout and stderr.
    """
    if isinstance(args, str):
        args = ["bash", "-c", args]
    p = sp.run(args, stdout=sp.PIPE, stderr=sp.PIPE, encoding="utf-8")
    if p.returncode != 0 and not error_ok:
        print(f"Failed to run [{' '.join(args)}]:", file=sys.stderr)
        print(p.stderr, file=sys.stderr, end="")
        sys.exit(p.returncode)
    return p.returncode, p.stdout, p.stderr


class SqliteDb:

    def __init__(self, target=None):
        self.target = target
        self.conn = sqlite3.connect(":memory:") if target is None else None

    def query(self, sql, data=None, named=False, one_row=False):
        """
        Query boilerplate reducer.
        :param sql str: SQL query
        :param data list: Optional query args
        :param one_row bool: If True, use cursor.fetchone() instead of fetchall()
        :param named bool: If True, rows are namedtuples
        """
        if self.conn:
            return self._query(self.conn, sql, data, named, one_row)
        else:
            with sqlite3.connect(self.target) as conn:
                return self._query(conn, sql, data, named, one_row)

    def _query(self, conn, sql, data=None, named=False, one_row=False):
        cur = conn.cursor()
        res = cur.execute(sql, data or [])
        if named:
            Row = co.namedtuple("Row", [col[0] for col in cur.description])
            if one_row:
                row = cur.fetchone()
                return row and Row(*row)
            else:
                rows = cur.fetchall()
                return [Row(*row) for row in rows]
        else:
            if one_row:
                return cur.fetchone()
            else:
                return cur.fetchall()

    def execute(self, sql, data=None):
        """
        Non-query boilerplate reducer.
        :param sql str: SQL query
        :param data list: Optional update args
        """
        if self.conn:
            self._execute(self.conn, sql, data or [])
        else:
            with sqlite3.connect(self.target) as conn:
                self._execute(conn, sql, data or [])

    def _execute(self, conn, sql, data):
        if len(data) > 0 and any(isinstance(data[0], x) for x in [list, tuple]):
            conn.cursor().executemany(sql, data)
        else:
            conn.cursor().execute(sql, data)


def from_footprint(x: str):
    """
    Translate a string a la 10K, 5Mb, 3Gi to # of bytes.
    """
    for suffix, mul in [("K",  10**3), ("M",  10**6), ("G",  10**9),
                        ("Ki", 2**10), ("Mi", 2**20), ("Gi", 2**30)]:
        if x.endswith(suffix):
            return mul * float(x.removesuffix(suffix))
    return float(x)


