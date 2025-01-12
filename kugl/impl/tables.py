"""
This is separate from engine.py for maintainability.
SQLite tables are defined and populated here.
"""

from typing import Optional, Type

import jmespath
from pydantic import Field, BaseModel

from .config import ColumnDef, ExtendTable, CreateTable

# TODO: make abstract
# TODO: completely sever from user configs
from ..util import fail, debugging


class TableDef(BaseModel):
    """
    Capture a table definition from the @table decorator, example:
        @table(schema="kubernetes", name="pods", resource="pods")
    """
    cls: Type
    name: str
    schema_name: str = Field(..., alias="schema")
    resource: str


class Table:
    """The engine-level representation of a table, independent of the config file format"""

    def __init__(self, name: str, schema_name, resource: str, ddl: str, extras: list[ColumnDef]):
        """
        :param name: the table name, e.g. "pods"
        :param name: the schema name, e.g. "kubernetes"
        :param resource: the Kubernetes resource type, e.g. "pods"
        :param ddl: SQL for creating the table, e.g. "name TEXT, age INTEGER"
        :param extras: extra column definitions from user configs (not from Python-defined tables)
        """
        self.name = name
        self.schema_name = schema_name
        self.resource = resource
        self.ddl = ddl
        self.extras = extras

    def build(self, db, kube_data: dict, multi_schema: bool):
        """Create the table in SQLite and insert the data.

        :param db: the SqliteDb instance
        :param kube_data: the JSON data from 'kubectl get'
        :param multi_schema: whether to use the schema name in the table name
        """
        context = RowContext(kube_data)
        table_name = f"{self.schema_name}.{self.name}" if multi_schema else self.name
        db.execute(f"CREATE TABLE {table_name} ({self.ddl})")
        item_rows = list(self.make_rows(context))
        if item_rows:
            if self.extras:
                extend_row = lambda item, row: row + tuple(column.extract(item, context) for column in self.extras)
            else:
                extend_row = lambda item, row: row
            rows = [extend_row(item, row) for item, row in item_rows]
            placeholders = ", ".join("?" * len(rows[0]))
            db.execute(f"INSERT INTO {table_name} VALUES({placeholders})", rows)

    @staticmethod
    def column_ddl(columns: list[ColumnDef]) -> str:
        return ", ".join(f"{c.name} {c._sqltype}" for c in columns)


class TableFromCode(Table):
    """A table created from Python code, not from a user config file."""

    def __init__(self, table_def: TableDef, extender: Optional[ExtendTable]):
        """
        :param table_def: a TableDef from the @table decorator
        :param extender: an ExtendTable object from the extend: section of a user config file
        """
        impl = table_def.cls()
        ddl = impl.ddl
        if extender:
            ddl += ", " + Table.column_ddl(extender.columns)
            extras = extender.columns
        else:
            extras = []
        if debug:= debugging("schema"):
            debug(f"table {table_def.name}: {ddl}")
        super().__init__(table_def.name, table_def.schema_name, table_def.resource, ddl, extras)
        self.impl = impl

    def make_rows(self, context: "RowContext") -> list[tuple[dict, tuple]]:
        """Delegate to the user-defined table implementation."""
        return self.impl.make_rows(context)


class TableFromConfig(Table):
    """A table created from a create: section in a user config file, rather than in Python"""

    def __init__(self, name: str, schema_name: str, creator: CreateTable, extender: Optional[ExtendTable]):
        """
        :param name: the table name, e.g. "pods"
        :param creator: a CreateTable object from the create: section of a user config file
        :param extender: an ExtendTable object from the extend: section of a user config file
        """
        if creator.row_source is None:
            # FIXME: kubernetes-specific
            self.itemizer = lambda data: data["items"]
        else:
            self.itemizer = lambda data: self._itemize(creator.row_source, data)
        schema = Table.column_ddl(creator.columns)
        extras = creator.columns
        if extender:
            schema += ", " + Table.column_ddl(extender.columns)
            extras += extender.columns
        super().__init__(name, schema_name, creator.resource, schema, extras)
        self.row_source = creator.row_source

    def make_rows(self, context: "RowContext") -> list[tuple[dict, tuple]]:
        """
        Itemize the data according to the configuration, but return empty rows; all the
        columns will be added by Table.build.
        """
        if self.row_source is not None:
            items = self._itemize(self.row_source, context)
        else:
            # FIXME: this default only applies to Kubernetes
            items = context.data["items"]
        return [(item, tuple()) for item in items]

    def _itemize(self, row_source: list[str], context: "RowContext") -> list[dict]:
        """
        Given a row_source like
          row_source:
            - items
            - spec.taints
        Iterate through each level of the source spec, marking object parents, and generating
        successive row values
        """
        items = [context.data]
        debug = debugging("itemize")
        for source in row_source:
            try:
                finder = jmespath.compile(source)
            except jmespath.exceptions.ParseError as e:
                fail(f"invalid row_source {source} for {self.name} table", e)
            new_items = []
            if debug:
                debug(f"itemizing {self.name} at {source} got {len(items)} hits")
            for item in items:
                found = finder.search(item)
                if isinstance(found, list):
                    for child in found:
                        context.set_parent(child, item)
                        new_items.append(child)
                elif found is not None:
                    context.set_parent(found, item)
                    new_items.append(found)
            items = new_items
        return items


class RowContext:
    """Provide helpers to row-generating functions.

    Primarily, the `.data` attribute holds the JSON data from 'kubectl get' or similar.
    The `.set_parent` and `.get_parent` methods allow row-generating functions to track
    parent objects as they iterate through nested data structures."""

    def __init__(self, data):
        self.data = data
        self.debug = debugging("extract")
        self._parents = {}

    def set_parent(self, child, parent):
        self._parents[id(child)] = parent

    def get_parent(self, child, depth: int = 1):
        while depth > 0 and child is not None:
            child = self._parents.get(id(child))
            depth -= 1
        return child

    def get_root(self, child):
        while (parent := self._parents.get(id(child))) is not None:
            child = parent
        return child

