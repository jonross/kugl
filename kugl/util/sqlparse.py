from collections import deque
from dataclasses import dataclass
from typing import Optional

import sqlparse
from sqlparse.tokens import Name, Comment, Punctuation

from kugl.util import fail, TABLE_NAME_RE, cleave


@dataclass(frozen=True)
class NamedTable:
    """Capture e.g. 'kubernetes.pods" as an object + make it hashable for use in sets."""
    schema_name: Optional[str]
    name: str

    def __post_init__(self):
        if self.schema_name in ["main", "temp", "init"]:
            fail("invalid schema name, must not be 'main', 'temp', or 'init'")
        if not TABLE_NAME_RE.match(self.name):
            fail(f"invalid table name in '{self}' -- must contain only letters, digits, and underscores")
        if self.schema_name and not TABLE_NAME_RE.match(self.schema_name):
            fail(f"invalid schema name in '{self}' -- must contain only letters, digits, and underscores")

    def __str__(self):
        return f"{self.schema_name}.{self.name}" if self.schema_name else self.name


class Tokens:
    """Hold a list of sqlparse tokens and provide a means to scan with or without skipping whitespace."""

    def __init__(self, tokens):
        self._unseen = deque(tokens)

    def get(self, skip: bool = True):
        """
        Get the next token from the list, or None if there are no more.
        :param skip: Skip over whitespace and comments.
        """
        while self._unseen:
            token = self._unseen.popleft()
            if skip and (token.is_whitespace or token.ttype is Comment):
                continue
            return token
        return None


class Query:
    """Hold a SQL query + information parsed from it using sqlparse."""

    def __init__(self, sql: str):
        self.sql = sql
        # Anything we found following FROM or JOIN.  May include CTEs, but that's OK.
        self.named_tables = set()
        self._scan()

    def schemas_named(self):
        """Return a set of schema names referenced in the query."""
        return {nt.schema_name for nt in self.named_tables if nt.schema_name}

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
        """Scan for a table name following FROM or JOIN and add it to self.named_tables.
        Don't skip whitespace, since the name parts should be adjacent."""
        if (token := tl.get()) is None:
            return
        name = token.value
        while (token := tl.get(skip=False)) and (token.ttype == Name or
                                                 token.ttype == Punctuation and token.value == "."):
            name += token.value
        self.named_tables.add(NamedTable(*cleave(name, ".", flip=True)))