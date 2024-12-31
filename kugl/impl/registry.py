"""
Registry of resources and tables, independent of configuration file format.
This is Kugl's global state outside the SQLite database.
"""
from argparse import ArgumentParser
from typing import Type

from pydantic import BaseModel, Field

from kugl.util import fail, dprint

_REGISTRY = None


class Registry:
    """All known tables and resources.
    There is one instance of this in any Kugl process."""

    def __init__(self):
        self.schemas = {}

    @staticmethod
    def get():
        global _REGISTRY
        if _REGISTRY is None:
            _REGISTRY = Registry()
        return _REGISTRY

    def add_schema(self, name: str, cls: Type):
        """Register a class to implement a schema; this is called by the @schema decorator."""
        dprint("registry", f"Add schema {name} {cls}")
        self.schemas[name] = Schema(name=name, impl=cls())

    def get_schema(self, name: str) -> "Schema":
        if name not in self.schemas:
            self.add_schema(name, GenericSchema)
        return self.schemas[name]

    def add_table(self, cls, **kwargs):
        """Register a class to define a table; this is called by the @table decorator."""
        dprint("registry", f"Add table {kwargs}")
        t = TableDef(cls=cls, **kwargs)
        if t.schema_name not in self.schemas:
            fail(f"Must create schema {t.schema_name} before table {t.schema_name}.{t.name}")
        self.schemas[t.schema_name].tables[t.name] = t


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


class GenericSchema:
    """get_schema auto-generates one of these when an undefined schema is referenced."""

    def add_cli_options(self, ap: ArgumentParser):
        # FIXME, artifact of assuming kubernetes
        self.ns = "default"
        pass

    def handle_cli_options(self, args):
        pass