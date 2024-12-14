
from typing import Type

from pydantic import BaseModel

from .utils import fail

_DOMAINS = {}


class TableDef(BaseModel):
    """
    Capture a table definition from the @table decorator, e.g.
        @table(domain="kubernetes", name="pods", resource="pods")
    """
    cls: Type
    name: str
    domain: str
    resource: str


class Domain:
    tables: dict[str, TableDef] = {}


def add_domain(self, name: str, cls: Type):
    """Register a class to implement a data domain; this is called by the @domain decorator."""
    _DOMAINS[name] = cls


def get_domain(name: str) -> Domain:
    return _DOMAINS[name]


def add_table(cls, **kwargs):
    """Register a table definition; this is called by the @table decorator."""
    t = TableDef(cls=cls, **kwargs)
    if t.domain not in _DOMAINS:
        fail(f"Must create domain {t.domain} before table {t.domain}.{t.name}")
    _DOMAINS[t.domain][t.name] = t