"""
Registry of resources and tables, independent of configuration file format.
This is Kugl's global state outside the SQLite database.
"""
from argparse import ArgumentParser
from typing import Type, Iterable

from pydantic import BaseModel

from kugl.impl.config import UserConfig, parse_file, CreateTable, ExtendTable, ResourceDef
from kugl.impl.tables import TableFromCode, TableFromConfig, TableDef, Table
from kugl.util import fail, debugging, ConfigPath, kugl_home

_REGISTRY = None


class Registry:
    """All known tables and resources.
    There is one instance of this in any Kugl process."""

    def __init__(self):
        self.schemas: dict[str, Schema] = {}
        self.resources_by_type: dict[str, type] = {}
        self.resources_by_schema: dict[str, type] = {}

    @staticmethod
    def get():
        global _REGISTRY
        if _REGISTRY is None:
            _REGISTRY = Registry()
        return _REGISTRY

    def add_schema(self, name: str, cls: Type):
        """Register a class to implement a schema; this is called by the @schema decorator."""
        if debug := debugging("registry"):
            debug(f"Add schema {name} {cls}")
        self.schemas[name] = Schema(name=name, impl=cls())

    def get_schema(self, name: str) -> "Schema":
        if name not in self.schemas:
            self.add_schema(name, GenericSchemaImpl)
        return self.schemas[name].augment()

    def add_table(self, cls: type, **kwargs):
        """Register a class to define a table in Python; this is called by the @table decorator."""
        if debug := debugging("registry"):
            debug(f"Add table {kwargs}")
        t = TableDef(cls=cls, **kwargs)
        if t.schema_name not in self.schemas:
            fail(f"Must create schema {t.schema_name} before table {t.schema_name}.{t.name}")
        self.schemas[t.schema_name].builtin[t.name] = t

    def add_resource(self, cls: type, name: str, schema_defaults: list[str]):
        """
        Register a resource type.  This is called by the @resource decorator.

        :param cls: The class to register
        :param name: e.g. "file", "kubernetes", "aws"
        :param schema_defaults: The schema names for which this is the default resource type.
            For type "file" this is an empty list because any schema can use a file resource,
                it's never the default.
            For type "kubernetes" this any schema that will use 'kubectl get' so e.g.
                ["kubernetes", "argo", "kueue", "karpenter"] et cetera
            It's TBD whether we will have a single common resource type for AWS resources, or
                if there will be one per AWS service.
        """
        existing = self.resources_by_type.get(name)
        if existing:
            fail(f"Resource type {name} already registered as {existing.__name__}")
        for schema_name in schema_defaults:
            existing = self.resources_by_schema.get(schema_name)
            if existing:
                fail(f"Resource type {name} already registered as the default for schema {schema_name}")
        self.resources_by_type[name] = cls
        for schema_name in schema_defaults:
            self.resources_by_schema[schema_name] = cls

    def augment_cli(self, ap: ArgumentParser):
        """Extend CLI argument parser with custom options per resource type."""
        for resource_class in set(self.resources_by_type.values()):
            if hasattr(resource_class, "add_cli_options"):
                resource_class.add_cli_options(ap)


class Schema(BaseModel):
    """Collection of tables and resource definitions.

    Capture a schema definition from the @schema decorator, example:
        @schema("kubernetes")
    Or, capture a schema definition in a user config file.
    Or both.
    """
    name: str
    impl: object # FIXME use type vars
    builtin: dict[str, TableDef] = {}
    _create: dict[str, CreateTable] = {}
    _extend: dict[str, ExtendTable] = {}
    _resources: dict[str, ResourceDef] = {}

    def augment(self):
        """Apply the built-in and user configuration files for the schema, if present."""
        def _apply(path: ConfigPath):
            if path.exists():
                config, errors = parse_file(UserConfig, path)
                if errors:
                    fail("\n".join(errors))
                self._create.update({c.table: c for c in config.create})
                self._extend.update({e.table: e for e in config.extend})
                self._resources.update({r.name: r for r in config.resources})

        # Reset the non-builtin tables, since these can change during unit tests.
        for mapping in [self._create, self._extend, self._resources]:
            mapping.clear()

        # Apply builtin config and user config
        _apply(ConfigPath(__file__).parent.parent / "builtins" / f"{self.name}.yaml")
        _apply(ConfigPath(kugl_home() / f"{self.name}.yaml"))

        # Verify user-defined tables have the needed resources
        for table in self._create.values():
            if table.resource not in self._resources:
                fail(f"Table '{table.table}' needs unknown resource '{table.resource}'")

        return self

    def table_builder(self, name):
        """Return the Table builder subclass (see tables.py) for a table name."""
        builtin = self.builtin.get(name)
        creator = self._create.get(name)
        extender = self._extend.get(name)
        if builtin and creator:
            fail(f"Pre-defined table {name} can't be created from config")
        if builtin:
            return TableFromCode(builtin, extender)
        if creator:
            return TableFromConfig(name, creator, extender)

    def resources_used(self, tables: Iterable[Table]) -> set[ResourceDef]:
        """Return the ResourceDefs used by the listed tables."""
        return {self._resources[t.resource] for t in tables}


class GenericSchemaImpl:
    """get_schema auto-generates one of these when an undefined schema is referenced."""
    ns: str = "default"  # FIXME

    def handle_cli_options(self, args):
        pass