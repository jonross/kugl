from collections import deque, namedtuple
from dataclasses import dataclass
from typing import Optional

import funcy as fn
import sqlparse
from sqlparse.sql import Token
from sqlparse.tokens import Name, Comment, Punctuation, Keyword

from kugl.util import fqtn, fail


@dataclass(frozen=True)
class TableRef:
    """Capture e.g. 'kubernetes.pods" as an object + make it hashable for use in sets."""
    schema_name: Optional[str]
    name: str

    def __str__(self):
        return f"{self.schema_name}.{self.name}" if self.schema_name else self.name


class Tokens:
    """Hold a list of sqlparse tokens and provide a means to scan with or without skipping whitespace."""

    def __init__(self, tokens):
        self._unseen = deque(tokens)
        self._seen = deque()

    def get(self, skip: bool = True):
        """
        Get the next token from the list, or None if there are no more.
        :param skip: Skip over whitespace and comments.
        """
        while self._unseen:
            token = self._unseen.popleft()
            self._seen.append(token)
            if skip and (token.is_whitespace or token.ttype is Comment):
                continue
            return token
        return None

    def join(self):
        return "".join(fn.concat(self._seen, self._unseen))

    @property
    def context(self):
        return " ".join(t.value for t in list(self._seen_nowhite)[-6:-1])


class Query:
    """Hold a SQL query + information parsed from it using sqlparse."""

    def __init__(self, sql: str):
        self.sql = sql
        # Anything we found following FROM or JOIN.  May include CTEs, but that's OK.
        self.refs = set()
        self._scan()

    @property
    def rebuilt(self):
        return self._tokens.join()

    def _scan(self):
        """Find table references."""

        statements = sqlparse.parse(self.sql)
        if len(statements) != 1:
            fail("query must contain exactly one statement")
        tl = Tokens(statements[0].flatten())

        while (token := tl.get()) is not None:
            if not token.is_keyword:
                continue
            keyword = token.value.upper()
            if keyword == "FROM" or keyword.endswith("JOIN"):
                self._scan_table_name(tl)

    def _scan_table_name(self, tl: Tokens):
        """Scan for a table name following FROM or JOIN and add it to self.refs.
        Don't skip whitespace, since the name parts should be adjacent."""
        if (token := tl.get()) is None:
            return
        name = token.value
        while (token := tl.get(skip=False)) and (token.ttype == Name or
                                                 token.ttype == Punctuation and token.value == "."):
            name += token.value
        parts = name.split(".")
        if len(parts) == 1:
            self.refs.add(TableRef(None, *parts))
        elif len(parts) == 2:
            self.refs.add(TableRef(*parts))
        else:
            fail(f"invalid schema name in table: {name}")
