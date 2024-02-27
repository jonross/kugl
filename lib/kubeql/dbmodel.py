
from dataclasses import dataclass
import jmespath

from .utils import rcfail


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
    # e.g. int
    type: ColumnType
    # e.g. "name"
    name: str
    # e.g. "pods"
    table_name: str
    # e.g. jmespath.compile("metadata.name")
    finder: jmespath.parser.ParsedResult

    def __call__(self, obj):
        return self.source.search(obj)

    @staticmethod
    def from_config(name: str, table_name: str, obj: dict):
        what = f"column '{name}' in table '{table_name}'"
        type, source = obj.get("type"), obj.get("source")
        if type is None or source is None:
            rcfail(f"missing type or source for {what}")
        type = COLUMN_TYPES.get(type)
        if type is None:
            rcfail(f"type of {what} must be one of {', '.join(COLUMN_TYPES.keys())}")
        if source == "-":
            finder = lambda obj: obj
        else:
            try:
                jmesexpr = jmespath.compile(source)
                finder = lambda obj: jmesexpr.search(obj)
            except jmespath.exceptions.ParseError as e:
                rcfail(f"invalid JMESPath expression for {what}: {e}")
        return Column(type, name, table_name, finder)

    def extract(self, obj):
        value = self.finder(obj)
        return None if value is None else self.type.converter(value)