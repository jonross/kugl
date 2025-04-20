"""
Registry of resources and tables, independent of configuration file format.
"""

from argparse import ArgumentParser
from collections import defaultdict
from itertools import chain
from typing import Type, Optional

from pydantic import BaseModel

from kugl.impl.config import UserConfig, parse_file, CreateTable, ExtendTable, ResourceDef, DEFAULT_SCHEMA, parse_model
from kugl.impl.tables import TableFromCode, TableFromConfig, TableDef, Table
from kugl.util import fail, debugging, ConfigPath, kugl_home, cleave, failure_preamble, KPath

_REGISTRY = None


class Registry:
    """All known tables and resources.
    There is one instance of this in any Kugl process."""

    def __init__(self):
        self.schemas: dict[str, Schema] = {}
        self.resources_by_family: dict[str, type] = {}
        self.resources_by_schema: dict[str, type] = {}

    @staticmethod
    def get():
        global _REGISTRY
        if _REGISTRY is None:
            _REGISTRY = Registry()
        return _REGISTRY

    def get_schema(self, name: str) -> "Schema":
        """Return the schema object for a schema name, creating it if necessary."""
        if name not in self.schemas:
            self.schemas[name] = Schema(name=name)
        return self.schemas[name]

    def add_table(self, cls: type, **kwargs):
        """Register a class to define a table in Python; this is called by the @table decorator."""
        t = TableDef(cls=cls, **kwargs)
        self.get_schema(t.schema_name).builtin[t.name] = t

    def add_resource(self, cls: type, family: str, schema_defaults: list[str]):
        """
        Register a resource type.  This is called by the @resource decorator.

        :param cls: The class to register
        :param family: e.g. "file", "kubernetes", "aws"
        :param schema_defaults: The schema names for which this is the default resource family.
            For type "file" this is an empty list because any schema can use a file resource,
                it's never the default.
            For type "kubernetes" this any schema that will use 'kubectl get' so e.g.
                ["kubernetes", "argo", "kueue", "karpenter"] et cetera
            It's TBD whether we will have a single common resource type for AWS resources, or
                if there will be one per AWS service.
        """
        if hasattr(cls, "add_cli_options") and not hasattr(cls, "handle_cli_options"):
            fail(f"Resource type {family} has add_cli_options method but not handle_cli_options")
        existing = self.resources_by_family.get(family)
        if existing:
            fail(f"Resource type {family} already registered as {existing.__name__}")
        for schema_name in schema_defaults:
            existing = self.resources_by_schema.get(schema_name)
            if existing:
                fail(f"Resource type {family} already registered as the default for schema {schema_name}")
        self.resources_by_family[family] = cls
        for schema_name in schema_defaults:
            self.resources_by_schema[schema_name] = cls

    def get_resource_by_family(self, family: str, error_ok: bool = False) -> Type:
        impl = self.resources_by_family.get(family)
        if not impl and not error_ok:
            fail(f"Resource family {family} is not registered")
        return impl

    def get_resource_by_schema(self, schema_name: str) -> Type:
        return self.resources_by_schema.get(schema_name)

    def augment_cli(self, ap: ArgumentParser):
        """Extend CLI argument parser with custom options per resource type."""
        for resource_class in set(self.resources_by_family.values()):
            if hasattr(resource_class, "add_cli_options"):
                resource_class.add_cli_options(ap)

    def printable_schema(self, arg: str, init_path: list[str]):
        schema_name, table_name = cleave(arg, ".")
        schema = self.get_schema(schema_name).read_configs(init_path)
        if table_name:
            return schema.table_builder(table_name, missing_ok=False).printable_schema()
        return "\n\n".join(schema.table_builder(name).printable_schema()
                         for name in sorted(schema.all_table_names()))


class Resource(BaseModel):
    """Common attributes of all resource types."""
    name: str
    # This is optional because the default cache behavior for every resource type is different.
    # We set it to None to detect when the user hasn't configured it.
    cacheable: Optional[bool] = None

    @classmethod
    def add_cli_options(cls, ap: ArgumentParser):
        pass

    def handle_cli_options(self, args):
        pass

    def get_objects(self):
        raise NotImplementedError(f"{self.__class__} must implement get_objects()")

    def cache_path(self):
        raise NotImplementedError(f"{self.__class__} must implement cache_path()")


class Schema(BaseModel):
    """Collection of tables and resource definitions."""
    name: str
    builtin: dict[str, TableDef] = {}
    _create: dict[str, CreateTable] = {}
    _extend: dict[str, ExtendTable] = {}
    _resources: dict[str, Resource] = {}

    def read_configs(self, init_path: list[str]):
        """Apply the built-in and user configuration files for the schema, if present."""

        init_path = [
            ConfigPath(__file__).parent.parent / "builtins" / "schemas",
            *[ConfigPath(p) for p in init_path],
            ConfigPath(kugl_home())
        ]

        # Reset the non-builtin tables, since these can change during unit tests.
        self._create.clear()
        self._extend.clear()
        self._resources.clear()

        # Establish the columns known per table, in order to detect duplicates
        tables_known = defaultdict(set)
        for table_def in self.builtin.values():
            columns_known = tables_known[table_def.name]
            for column in table_def.cls().columns():
                columns_known.add(column.name)

        def _check_column(table_name, column_name):
            # Detect duplicate columns
            columns_known = tables_known[table_name]
            if column_name in columns_known:
                fail(f"Column '{column_name}' is already defined in table '{table_name}'")
            columns_known.add(column_name)

        def _apply(folder: ConfigPath):
            # Merge one UserConfig into the schema.
            path = folder / f"{self.name}.yaml"
            if not path.exists():
                return False
            with failure_preamble(f"Errors in {path}:"):
                config = parse_file(UserConfig, path)
                for r in config.resources:
                    # Detect duplicate resource
                    if r.name in self._resources:
                        fail(f"Resource '{r.name}' is already defined in schema '{self.name}'")
                    # Infer resource type
                    self._resources[r.name] = self._find_resource(r)
                for c in config.create:
                    # Detect duplicate table
                    if c.table in tables_known:
                        fail(f"Table '{c.table}' is already defined in schema '{self.name}'")
                    # Detect unknown resource
                    if c.resource not in self._resources:
                        fail(f"Table '{c.table}' needs undefined resource '{c.resource}'")
                    # Detect duplicate column
                    for column in c.columns:
                        _check_column(c.table, column.name)
                    self._create[c.table] = c
                for e in config.extend:
                    # Detect unknown table
                    if e.table not in tables_known:
                        fail(f"Table '{e.table}' is not defined in schema '{self.name}'")
                    # Detect duplicate column
                    for column in e.columns:
                        _check_column(e.table, column.name)
                    self._extend[e.table] = e
            return True

        # Apply builtin config and user config.
        found = any([_apply(folder) for folder in init_path])
        if not found and self.name != DEFAULT_SCHEMA:
            # There's a built-in schema for Kubernetes, so no issue if no config files
            fail(f"no configurations found for schema '{self.name}'")

        return self

    def _find_resource(self, r: ResourceDef) -> Resource:
        """Return a Resource subclass instance for a table's resource name."""
        rgy = Registry.get()
        fields = r.model_dump()
        if "namespaced" in fields:
            return parse_model(rgy.get_resource_by_family("kubernetes"), fields)
        for family in ["file", "folder", "exec", "data"]:
            if family in fields:
                return parse_model(rgy.get_resource_by_family(family), fields)
        # If no family is specified, the schema may have a default one
        if (impl := rgy.get_resource_by_schema(self.name)):
            return parse_model(impl, fields)
        fail(f"can't infer type of resource '{r.name}' -- need one of 'file', 'data', 'namespaced' etc")

    def table_builder(self, name, missing_ok=True):
        """Return the Table builder subclass (see tables.py) for a table name.
        :param missing_ok: Defaults to True because we normally let SQLite flag missing tables.
        """
        builtin = self.builtin.get(name)
        creator = self._create.get(name)
        extender = self._extend.get(name)
        if builtin and creator:
            fail(f"Pre-defined table {name} can't be created from config")
        if builtin:
            return TableFromCode(builtin, extender)
        if creator:
            return TableFromConfig(name, self.name, creator, extender)
        if not missing_ok:
            fail(f"Table '{name}' is not defined in schema {self.name}")

    def all_table_names(self):
        return set(chain(self.builtin.keys(), self._create.keys(), self._extend.keys()))

    def resource_for(self, table: Table) -> set[ResourceDef]:
        """Return the ResourceDef used by a Table."""
        return self._resources[table.resource]