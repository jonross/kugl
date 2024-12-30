"""
Our entire interface to SQLite features is here.
"""

import collections as co
import sqlite3

from kugl.util import dprint


class SqliteDb:

    def __init__(self, target=None):
        self.target = target
        self.conn = sqlite3.connect(":memory:", check_same_thread=False) if target is None else None

    def query(self, sql, **kwargs):
        """
        Query boilerplate reducer.
        :param sql str: SQL query
        :param data list: Optional query args
        :param one_row bool: If True, use cursor.fetchone() instead of fetchall()
        :param named bool: If True, rows are namedtuples
        :param names list: If an array, append column names to it
        """
        dprint("sqlite", f"Query: {sql}")
        if self.conn:
            return self._query(self.conn, sql, **kwargs)
        else:
            with sqlite3.connect(self.target) as conn:
                return self._query(conn, sql, **kwargs)

    def _query(self, conn, sql, data=None, named=False, names=None, one_row=False):
        cur = conn.cursor()
        res = cur.execute(sql, data or [])
        if names is not None:
            names.extend(col[0] for col in cur.description)
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
        dprint("sqlite", f"Execute: {sql}")
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

