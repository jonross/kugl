"""
Imports usable by user-defined tables in Python (once we have those.)
"""

from kugl.impl.registry import Registry, Resource

from kugl.util import (
    fail,
    parse_age,
    parse_utc,
    run,
    to_age,
    to_utc,
)


def resource(type: str, schema_defaults: list[str] = []):
    def wrap(cls):
        Registry.get().add_resource(cls, type, schema_defaults)
        return cls
    return wrap


def table(**kwargs):
    def wrap(cls):
        Registry.get().add_table(cls, **kwargs)
        return cls
    return wrap

