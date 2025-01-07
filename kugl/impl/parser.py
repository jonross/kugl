from collections import deque, namedtuple
import sqlparse
from sqlparse.sql import Token
from sqlparse.tokens import Name, Comment, Punctuation

TableRef = namedtuple("TableRef", ["schema", "name"])


class Tokens:
    """Hold a list of sqlparse tokens and provide a get/unget interface.
    This uses two deques so it allows unget of multiple tokens, or insertion of new tokens."""

    def __init__(self, tokens):
        self._seen = deque()
        self._unseen = deque(tokens)

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

    def unget(self):
        """Put the last token back."""
        if self._seen:
            self._unseen.appendleft(self._seen.pop())


class KQuery:

    def __init__(self, sql: str):
        self.ctes = set()
        self.tables = set()
        s = sqlparse.parse(sql.lower())
        if len(s) != 1:
            raise ValueError("SQL must contain exactly one statement")
        self._scan(Tokens(s[0].flatten()))

    def _scan(self, tl: Tokens):

        def scan_statement():
            """Scan tokens at the root of a query string or inside ( )"""
            token = tl.get()
            if token.is_keyword and token.value == "with":
                scan_ctes()
            while (token := tl.get()) is not None:
                if token.is_keyword and token.value in ("from", "join"):
                    scan_table_name()
                elif token.ttype is Punctuation:
                    if token.value == "(":
                        scan_statement()
                    elif token.value == ")":
                        return

        def scan_ctes():
            t = tl.get()
            if t.value == "recursive":
                t = tl.get()
            self.ctes.add(get_identifier(t, "CTE name", False))
            # TO DO handle multiple expressions

        def scan_table_name():
            pass

        def get_identifier(t: Token, expectation: str, allow_prefix: bool):
            if t.ttype is not Name:
                raise ValueError(f"expected {expectation} but got {t.value}")
            # Allow table names of the form "kub.pods"
            dot = tl.get(False)
            if dot.value != ".":
                tl.unget()
                return t.value
            if not allow_prefix:
                raise ValueError("CTE names may not have schema prefixes")
            suffix = tl.get(False)
            if suffix.ttype is not Name:
                raise ValueError(f"expected more to {expectation} '{t.value}.' but got {suffix.value}")
            return f"{t.value}.{suffix.value}"

        scan_statement()

