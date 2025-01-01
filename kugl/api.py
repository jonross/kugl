"""
Imports usable by user-defined tables in Python (once we have those.)
"""

from kugl.impl.registry import Registry

from kugl.util import (
    fail,
    parse_age,
    parse_utc,
    to_age,
    to_utc,
)


def schema(name: str):
    def wrap(cls):
        Registry.get().add_schema(name, cls)
        return cls
    return wrap


def table(**kwargs):
    def wrap(cls):
        Registry.get().add_table(cls, **kwargs)
        return cls
    return wrap

