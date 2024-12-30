"""
Registry of resources and tables, independent of configuration file format.
This is Kugl's global state outside the SQLite database.
"""
import json
import sys
from argparse import ArgumentParser
from typing import Type

import yaml
from pydantic import BaseModel, Field

from kugl.util import fail, dprint

_SCHEMAS = {}


def schema(name: str):
    def wrap(cls):
        add_schema(name, cls)
        return cls
    return wrap


def table(**kwargs):
    def wrap(cls):
        add_table(cls, **kwargs)
        return cls
    return wrap


class TableDef(BaseModel):
    """
    Capture a table definition from the @table decorator, example:
        @table(schema="kubernetes", name="pods", resource="pods")
    """
    cls: Type
    name: str
    schema_name: str = Field(..., alias="schema")
    resource: str


class Schema(BaseModel):
    """
    Capture a schema definition from the @schema decorator, example:
        @schema("kubernetes")
    """
    name: str
    impl: object # FIXME use type vars
    tables: dict[str, TableDef] = {}


def add_schema(name: str, cls: Type):
    """Register a class to implement a schema; this is called by the @schema decorator."""
    dprint("registry", f"Add schema {name} {cls}")
    _SCHEMAS[name] = Schema(name=name, impl=cls())


def get_schema(name: str) -> Schema:
    if name not in _SCHEMAS:
        add_schema(name, GenericSchema)
    return _SCHEMAS[name]


def add_table(cls, **kwargs):
    """Register a class to define a table; this is called by the @table decorator."""
    dprint("registry", f"Add table {kwargs}")
    t = TableDef(cls=cls, **kwargs)
    if t.schema_name not in _SCHEMAS:
        fail(f"Must create schema {t.schema_name} before table {t.schema_name}.{t.name}")
    _SCHEMAS[t.schema_name].tables[t.name] = t


class GenericSchema:
    """get_schema auto-generates one of these when an undefined schema is referenced."""

    def add_cli_options(self, ap: ArgumentParser):
        # FIXME, artifact of assuming kubernetes
        self.ns = "default"
        pass

    def handle_cli_options(self, args):
        pass

    def get_objects(self, *_):
        text = sys.stdin.read()
        if not text:
            return {}
        if text[0] in "{[":
            return json.loads(text)
        return yaml.safe_load(text)
