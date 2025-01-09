from collections import deque, namedtuple
from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Token
from sqlparse.tokens import Name, Comment, Punctuation, Keyword


@dataclass
class TableRef:
    schema: str
    name: str

    def __hash__(self):
        return hash((self.schema, self.name))

    def __eq__(self, other):
        return self.schema == other.schema and self.name == other.name

    def __str__(self):
        return f"{self.schema}.{self.name}"


class Tokens:
    """Hold a list of sqlparse tokens and provide a get/unget interface.
    This uses two deques so it allows unget of multiple tokens, or insertion of new tokens."""

    def __init__(self, tokens):
        self._unseen = deque(tokens)
        self._seen = deque()
        self._seen_nowhite = deque()

    def get(self, skip: bool = True):
        """
        Get the next token from the list, or None if there are no more.
        :param skip: Skip over whitespace and comments.
        """
        while self._unseen:
            token = self._unseen.popleft()
            self._seen.append(token)
            if token.is_whitespace or token.ttype is Comment:
                if skip:
                    continue
            else:
                self._seen_nowhite.append(token)
            return token
        return None

    def unget(self):
        """Put the last token back."""
        if self._seen:
            self._unseen.appendleft(self._seen.pop())

    def expected(self, expected: str, got: Token):
        print("got", got)
        raise ValueError(f"expected {expected} after <{self.context}> but got <{got and got.value}>")

    @property
    def context(self):
        return " ".join(t.value for t in list(self._seen_nowhite)[-6:-1])


class KQuery:

    """
    See https://www.sqlite.org/lang.html
    """

    def __init__(self, sql: str, default_schema: str):
        self.ctes = set()
        self.tables = set()
        self.default_schema = default_schema
        s = sqlparse.parse(sql.lower())
        if len(s) != 1:
            raise ValueError("SQL must contain exactly one statement")
        self._scan(Tokens(s[0].flatten()))

    def _scan(self, tl: Tokens):

        def scan_statement():
            """Scan tokens at the root of a query string or inside ( ), the latter assuming the caller
            has already read the opening parenthesis."""
            if (token := tl.get()) is None:
                return
            if token.is_keyword and token.value == "with":
                scan_cte()
            # Zero or more CTEs have been read, select should follow.
            while (token := tl.get()) is not None:
                # Look for FROM, JOIN, or e.g. OUTER JOIN which sqlparse represents as one keyword
                if token.is_keyword and (token.value in ("from", "join") or token.value.endswith(" join")):
                    table_name = get_identifier(tl.get(), False)
                    if table_name in self.ctes:
                        pass  # nothing to do, name is already defined
                    elif "." in table_name:
                        self.tables.add(TableRef(*table_name.split(".")))
                    else:
                        self.tables.add(TableRef(self.default_schema, table_name))
                elif token.ttype is Punctuation:
                    if token.value == "(":
                        scan_statement()
                    elif token.value == ")":
                        # Return from recursive invocation.  No worry if ( ) are unbalanced, since SQLite
                        # will reject that.
                        return

        def scan_cte():
            """Scan one CTEs, seeking the name and body.  The caller has already read the WITH keyword.
            Recursively invokes scan_statement for the body, then scan_ctes for additional CTEs."""
            # Syntax is
            #   WITH [RECURSIVE] cte_name AS [NOT [MATERIALIZED]] (select ...)
            if (token := tl.get()) is None:
                tl.expected("CTE name", token)
            if token.value == "recursive":
                token = tl.get()
            cte_name = get_identifier(token, True)
            self.ctes.add(cte_name)
            token = tl.get()
            if not token or not token.is_keyword or token.value != "as":
                tl.expected("keyword AS", token)
            token = tl.get()
            # This is a bug, sqlparser thinks MATERIALIZED isn't a keyword
            if token and token.ttype in (Name, Keyword):
                if token.value == "materialized":
                    token = tl.get()
                elif token.value == "not":
                    token = tl.get()
                    if not token or token.ttype not in (Name, Keyword) or token.value != "materialized":
                        tl.expected("keyword MATERIALIZED", token)
                    token = tl.get()
            if not token or token.ttype is not Punctuation or token.value != "(":
                tl.expected("CTE body", token)
            # Get the select statement inside ( ) then see if there is a comma for another CTE.
            scan_statement()
            token = tl.get()
            if not token:
                return
            if token.ttype is Punctuation and token.value == ",":
                scan_cte()
            else:
                scan_statement()

        def get_identifier(token: Token, for_cte: bool):
            if token.ttype is not Name:
                tl.expected("CTE name" if for_cte else "table name", token)
            # Allow table names of the form "kub.pods"
            dot = tl.get(False)
            if dot.ttype is not Punctuation or dot.value != ".":
                tl.unget()
                return token.value
            if for_cte:
                raise ValueError("CTE names may not have schema prefixes")
            suffix = tl.get(False)
            if suffix.ttype is not Name:
                raise ValueError(f"invalid schema.table name: '{token.value}.{suffix.value}'")
            return f"{token.value}.{suffix.value}"

        scan_statement()

