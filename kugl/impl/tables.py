"""
This is separate from engine.py for maintainability.
SQLite tables are defined and populated here.
"""
from dataclasses import dataclass
from typing import Optional, Type

import jmespath
from jmespath.parser import ParsedResult
from pydantic import Field, BaseModel
from tabulate import tabulate

from .config import UserColumn, ExtendTable, CreateTable, Column
from ..util import fail, debugging, abbreviate


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

    def __init__(self, name: str, schema_name, resource: str,
                 builtin_columns: list[Column], non_builtin_columns: list[UserColumn]):
        """
        :param name: the table name, e.g. "pods"
        :param name: the schema name, e.g. "kubernetes"
        :param resource: the Kubernetes resource type, e.g. "pods"
        """
        self.name = name
        self.schema_name = schema_name
        self.resource = resource
        self.builtin_columns = builtin_columns
        self.non_builtin_columns = non_builtin_columns

    def build(self, db, kube_data: dict, multi_schema: bool):
        """Create the table in SQLite and insert the data.

        :param db: the SqliteDb instance
        :param kube_data: the JSON data from 'kubectl get'
        :param multi_schema: whether to use the schema name in the table name
        """
        context = RowContext(kube_data)
        table_name = f"{self.schema_name}.{self.name}" if multi_schema else self.name
        ddl = ", ".join(f"{c.name} {c._sqltype}" for c in self.builtin_columns + self.non_builtin_columns)
        db.execute(f"CREATE TABLE {table_name} ({ddl})")
        item_rows = list(self.make_rows(context))
        if item_rows:
            if self.non_builtin_columns:
                extend_row = lambda item, row: row + tuple(column.extract(item, context)
                                                           for column in self.non_builtin_columns)
            else:
                extend_row = lambda item, row: row
            rows = [extend_row(item, row) for item, row in item_rows]
            placeholders = ", ".join("?" * len(rows[0]))
            db.execute(f"INSERT INTO {table_name} VALUES({placeholders})", rows)

    def printable_schema(self):
        rows = [(c.name, c._sqltype, c.comment or "") for c in self.builtin_columns + self.non_builtin_columns]
        return f"## {self.name}\n" + tabulate(rows, tablefmt="plain")


class TableFromCode(Table):
    """A table created from Python code, not from a user config file."""

    def __init__(self, table_def: TableDef, extender: Optional[ExtendTable]):
        """
        :param table_def: a TableDef from the @table decorator
        :param extender: an ExtendTable object from the extend: section of a user config file
        """
        self.impl = table_def.cls()
        super().__init__(table_def.name, table_def.schema_name, table_def.resource, self.impl.columns(),
                         extender.columns if extender else [])

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
        super().__init__(name, schema_name, creator.resource, [],
                         creator.columns + (extender.columns if extender else []))
        self.row_source = [Itemizer.parse(x, name) for x in (creator.row_source or ["items"])]

    def make_rows(self, context: "RowContext") -> list[tuple[dict, tuple]]:
        """
        Itemize the data according to the configuration, but return empty rows; all the
        columns will be added by Table.build.
        """
        items = self._itemize(context)
        return [(item, tuple()) for item in items]

    def _itemize(self, context: "RowContext") -> list[dict]:
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
        if debug:
            debug("begin itemization with " + abbreviate(items))
        for index, source in enumerate(self.row_source):
            if debug:
                debug(f"pass {index + 1}, row_source selector = {source.expr}")
            new_items = []
            for item in items:
                found = source.finder.search(item)
                if isinstance(found, dict) and source.unpack:
                    found = [{"key": k, "value": v} for k, v in found.items()]
                if isinstance(found, list):
                    for child in found:
                        if index > 0:
                            # Fix #132 -- don't do this at pass 0, or it sets the parent to the entire
                            # response object, breaking self.get_root()
                            context.set_parent(child, item)
                        new_items.append(child)
                        if debug:
                            debug("add " + abbreviate(child))
                elif found is not None:
                    if index > 0:
                        # See comment above.
                        context.set_parent(found, item)
                    new_items.append(found)
                    if debug:
                        debug("add " + abbreviate(found))
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


@dataclass
class Itemizer:
    """Helper class to hold information parsed from one line of a row_source"""
    # Original row_source expression
    expr: str
    # JMESPath expression to find the items
    finder: ParsedResult
    # Should dictionaries be unpacked to a key/value array
    unpack: bool

    @classmethod
    def parse(cls, s: str, table_name: str):
        """Parse a line from the row_source section of a config file"""
        parts = s.split(";")
        if len(parts) == 1:
            unpack = False
        elif len(parts) == 2 and parts[1].strip() == "kv":
            unpack = True
        else:
            fail(f"Invalid row_source options: {s}")
        try:
            return Itemizer(s, jmespath.compile(parts[0]), unpack)
        except jmespath.exceptions.ParseError as e:
            fail(f"invalid row_source {parts[0]} for table {table_name}", e)

