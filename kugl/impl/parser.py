from collections import deque, namedtuple
import sqlparse
from sqlparse.sql import Token
from sqlparse.tokens import Name, Comment, Punctuation

TableRef = namedtuple("TableRef", ["schema", "name"])


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

    def expected(self, expected: str, but_got: str):
        raise ValueError(f"expected {expected} after <{self.context}> but got <{but_got}>")

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
            token = tl.get()
            if token.is_keyword and token.value == "with":
                scan_cte()
            # Zero or more CTEs have been read, select should follow.
            while (token := tl.get()) is not None:
                if token.is_keyword and token.value in ("from", "join"):
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
            t = tl.get()
            if t.value == "recursive":
                t = tl.get()
            cte_name = get_identifier(t, True)
            self.ctes.add(cte_name)
            t = tl.get()
            if not t.is_keyword or t.value != "as":
                tl.expected("keyword AS", t.value)
            t = tl.get()
            if t.ttype is Name:
                if t.value == "materialized":
                    t = tl.get()
                elif t.value == "not":
                    t = tl.get()
                    if t.ttype is not Name or t.value != "materialized":
                        tl.expected("keyword MATERIALIZED", t.value)
                    t = tl.get()
            if t.ttype is not Punctuation or t.value != "(":
                tl.expected("CTE body", t.value)
            # Get the select statement inside ( ) then see if there is a comma for another CTE.
            scan_statement()
            t = tl.get()
            if t.ttype is Punctuation and t.value == ",":
                scan_cte()
            else:
                scan_statement()

        def get_identifier(t: Token, for_cte: bool):
            if t.ttype is not Name:
                tl.expected("CTE name" if for_cte else "table name", t.value)
            # Allow table names of the form "kub.pods"
            dot = tl.get(False)
            if dot.ttype is not Punctuation or dot.value != ".":
                tl.unget()
                return t.value
            if for_cte:
                raise ValueError("CTE names may not have schema prefixes")
            suffix = tl.get(False)
            if suffix.ttype is not Name:
                raise ValueError(f"invalid schema.table name: '{t.value}.{suffix.value}'")
            return f"{t.value}.{suffix.value}"

        scan_statement()

