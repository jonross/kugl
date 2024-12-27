from typing import Optional

import jmespath

from .config import ColumnDef, ExtendTable, CreateTable

# TODO: make abstract
# TODO: completely sever from user configs
from .registry import TableDef
from ..util import fail, dprint, debugging


class Table:
    """The engine-level representation of a table, independent of the config file format"""

    def __init__(self, name: str, resource: str, schema: str, extras: list[ColumnDef]):
        """
        :param name: the table name, e.g. "pods"
        :param resource: the Kubernetes resource type, e.g. "pods"
        :param schema: the SQL schema, e.g. "name TEXT, age INTEGER"
        :param extras: extra column definitions from user configs (not from Python-defined tables)
        """
        self.name = name
        self.resource = resource
        self.schema = schema
        self.extras = extras

    def build(self, db, kube_data: dict):
        """Create the table in SQLite and insert the data.

        :param db: the SqliteDb instance
        :param kube_data: the JSON data from 'kubectl get'
        """
        context = RowContext(kube_data)
        db.execute(f"CREATE TABLE {self.name} ({self.schema})")
        item_rows = list(self.make_rows(context))
        if item_rows:
            if self.extras:
                extend_row = lambda item, row: row + tuple(column.extract(item, context) for column in self.extras)
            else:
                extend_row = lambda item, row: row
            rows = [extend_row(item, row) for item, row in item_rows]
            placeholders = ", ".join("?" * len(rows[0]))
            db.execute(f"INSERT INTO {self.name} VALUES({placeholders})", rows)

    @staticmethod
    def column_schema(columns: list[ColumnDef]) -> str:
        return ", ".join(f"{c.name} {c._sqltype}" for c in columns)


class TableFromCode(Table):
    """A table created from Python code, not from a user config file."""

    def __init__(self, table_def: TableDef, extender: Optional[ExtendTable]):
        """
        :param table_def: a TableDef from the @table decorator
        :param extender: an ExtendTable object from the extend: section of a user config file
        """
        impl = table_def.cls()
        schema = impl.schema
        if extender:
            schema += ", " + Table.column_schema(extender.columns)
            extras = extender.columns
        else:
            extras = []
        dprint("schema", f"Table {table_def.name} schema: {schema}")
        super().__init__(table_def.name, table_def.resource, schema, extras)
        self.impl = impl

    def make_rows(self, context: "RowContext") -> list[tuple[dict, tuple]]:
        """Delegate to the user-defined table implementation."""
        return self.impl.make_rows(context)


class TableFromConfig(Table):
    """A table created from a create: section in a user config file, rather than in Python"""

    def __init__(self, name: str, creator: CreateTable, extender: Optional[ExtendTable]):
        """
        :param name: the table name, e.g. "pods"
        :param creator: a CreateTable object from the create: section of a user config file
        :param extender: an ExtendTable object from the extend: section of a user config file
        """
        if creator.row_source is None:
            self.itemizer = lambda data: data["items"]
        else:
            self.itemizer = lambda data: self._itemize(creator.row_source, data)
        schema = Table.column_schema(creator.columns)
        extras = creator.columns
        if extender:
            schema += ", " + Table.column_schema(extender.columns)
            extras += extender.columns
        super().__init__(name, creator.resource, schema, extras)
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
                print(f"Itemizing {self.name} at {source} got {len(items)} hits")
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
    """One of these is passed to row-generating and column-extracting functions.
    It provides information like the parent map for evaluating JMESPath expressions, and
    removes the risk of changing row and column function signatures in the future."""

    def __init__(self, data):
        self.data = data
        self._parents = {}

    def set_parent(self, child, parent):
        self._parents[id(child)] = parent

    def get_parent(self, child):
        return self._parents.get(id(child))


