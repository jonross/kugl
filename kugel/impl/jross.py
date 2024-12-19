# These are from my personal library and are under the MIT license.
# They have no unit tests in Kugel because they are tested elsewhere.


import collections as co
import re
import sqlite3
import subprocess as sp
import sys
from typing import List, Union


def run(args: Union[str, List[str]], error_ok=False):
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


SIZE_RE = re.compile(r"([0-9.]+)(([A-Za-z]+)?)")
SIZE_MULTIPLIERS = dict(K=10**3, M=10**6, G=10**9, T=10**12,
                        Ki=2**10, Mi=2**20, Gi=2**30, Ti=2**40)

def from_footprint(x: Union[str, int, None]):
    """
    Translate a string a la 10K, 5Mb, 3Gi to # of bytes.  Returns an int if the result
    can be represented as an int, else a float.
    """
    if x is None:
        return None
    if isinstance(x, int):
        return x
    m = SIZE_RE.match(x)
    if m is None:
        raise ValueError(f"Can't translate {x} to a size")
    amount, suffix = m.group(1), m.group(2)
    amount = float(amount) if "." in amount else int(amount)
    if suffix == "m":
        return amount / 1000
    if suffix == "":
        return amount
    multiplier = SIZE_MULTIPLIERS.get(suffix)
    if multiplier is None:
        raise ValueError(f"Unknown size suffix in {x}")
    return int(amount * multiplier)


def to_footprint(nbytes: int, iec=False):
    """
    Given a byte count, render it as a string in the most appropriate units, suffixed by KB, MB, GB, etc.
    Larger sizes will use the appropriate unit.  The result may have a maximum of one digit after the
    decimal point.  If iec is True, use IEC binary units (KiB, MiB, etc).
    """
    one_k = 1024 if iec else 1000
    bytes = "iB" if iec else "B"
    if nbytes < one_k:
        return f"{nbytes}B"
    elif nbytes < one_k ** 2:
        size, suffix = nbytes / one_k, "K" + bytes
    elif nbytes < one_k ** 3:
        size, suffix = nbytes / one_k ** 2, "M" + bytes
    elif nbytes < one_k ** 4:
        size, suffix = nbytes / one_k ** 3, "G" + bytes
    else:
        size, suffix = nbytes / one_k ** 4, "T" + bytes
    if size < 10:
        return f"{size:.1f}{suffix}"
    else:
        return f"{round(size)}{suffix}"