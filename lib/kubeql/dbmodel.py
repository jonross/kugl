
from dataclasses import dataclass
import jmespath

from .utils import rcfail, MyConfig


@dataclass
class ColumnType:
    sql_type: str
    converter: callable


COLUMN_TYPES = {
    "str": ColumnType("TEXT", str),
    "int": ColumnType("INTEGER", int),
    "float": ColumnType("REAL", float),
}


@dataclass
class Column:
    # The SQLite type for this column, represented by a member of COLUMN_TYPES, above.
    type: ColumnType
    # The column name
    name: str
    # The table name
    table_name: str
    # How to extract the column value from an item in a Kubernetes API response list.
    # Example finder: jmespath.compile("metadata.name")
    finder: jmespath.parser.ParsedResult

    @staticmethod
    def from_config(name: str, table_name: str, obj: dict):
        what = f"column '{name}' in table '{table_name}'"
        type, source = obj.get("type"), obj.get("source")
        if type is None or source is None:
            rcfail(f"missing type or source for {what}")
        type = COLUMN_TYPES.get(type)
        if type is None:
            rcfail(f"type of {what} must be one of {', '.join(COLUMN_TYPES.keys())}")
        try:
            jmesexpr = jmespath.compile(source)
            finder = lambda obj: jmesexpr.search(obj)
        except jmespath.exceptions.ParseError as e:
            rcfail(f"invalid JMESPath expression for {what}: {e}")
        return Column(type, name, table_name, finder)

    def extract(self, obj):
        value = self.finder(obj)
        return None if value is None else self.type.converter(value)


class Table:
    """
    Turn 'kubectl get ... -o json" output into a database table.  Subclasses define
        NAME        the table name
        SCHEMA      chunk of DDL with column names and types
        make_rows   method to convert kubectl output into rows
    """

    def create(self, db, config: MyConfig, kube_data: dict):
        schema = self.SCHEMA
        extra_columns = [Column.from_config(name, self.NAME, detail)
                         for name, detail in config.extra_columns(self.NAME).items()]
        if extra_columns:
            schema += " ".join(f", {column.name} {column.type.sql_type}"
                               for column in extra_columns)
        db.execute(f"CREATE TABLE {self.NAME} ({schema})")
        rows = self.make_rows(kube_data["items"])
        if rows:
            if extra_columns:
                rows = [row + tuple(column.extract(item) for column in extra_columns)
                        for item, row in zip(kube_data["items"], rows)]
            placeholders = ", ".join("?" * len(rows[0]))
            db.execute(f"INSERT INTO {self.NAME} VALUES({placeholders})", rows)
