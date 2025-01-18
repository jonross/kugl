"""
Imports usable by user-defined tables in Python (once we have those.)
"""
from typing import Optional as _Optional

from kugl.impl.config import Column as _BuiltinColumn
from kugl.impl.registry import Registry as _Registry, Resource

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
        _Registry.get().add_resource(cls, type, schema_defaults)
        return cls
    return wrap


def table(**kwargs):
    def wrap(cls):
        _Registry.get().add_table(cls, **kwargs)
        return cls
    return wrap


def column(name: str, type: str, comment: _Optional[str] = None):
    return _BuiltinColumn(name=name, type=type.lower(), comment=comment)