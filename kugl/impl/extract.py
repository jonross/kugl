"""
Logic to extract column values from YAML fields.
Formerly in ./config.py, refactored for clarity.
"""

from dataclasses import dataclass
import re
from typing import Literal

import jmespath

from kugl.util import parse_utc, parse_age, parse_size, parse_cpu, abbreviate, fail

ColumnType = Literal["text", "integer", "real", "date", "age", "size", "cpu"]
PARENTED_PATH = re.compile(r"^(\^*)(.*)")

KUGL_TYPE_CONVERTERS = {
    # Valid choices for column type in config -> function to extract that from a string
    "integer": int,
    "real" : float,
    "text": str,
    "date": parse_utc,
    "age": parse_age,
    "size": parse_size,
    "cpu": parse_cpu,
}

KUGL_TYPE_TO_SQL_TYPE = {
    # Valid choices for column type in config -> SQLite type to hold it
    "integer": "integer",
    "real": "real",
    "text": "text",
    "date": "integer",
    "age": "integer",
    "size": "integer",
    "cpu": "real",
}


@dataclass
class FieldRef:
    """Parsed form of a parented JMESPath expression or label, e.g. '^^metadata.name'"""
    n_parents: int
    target: str

    @classmethod
    def parse(cls, s):
        m = PARENTED_PATH.match(s)
        return cls(len(m.group(1)), m.group(2))


class Extractor:
    """Base class for YAML field -> column value extractor"""

    def __init__(self, column_name: str, column_type: ColumnType):
        self.column_name = column_name
        self.column_type = column_type
        self._converter = KUGL_TYPE_CONVERTERS[column_type]

    def __call__(self, obj: object, context) -> object:
        """Extract the column value from an object and convert to the correct type."""
        if obj is None:
            if context.debug:
                context.debug(f"no object provided to extractor {self}")
            return None
        if context.debug:
            context.debug(f"get {self} from {abbreviate(obj)}")
        value = self.extract(obj, context)
        result = None if value is None else self._converter(value)
        if context.debug:
            context.debug(f"got {result}")
        return result


class LabelExtractor(Extractor):
    """Extract a column value from the first matching label in a list of labels."""

    def __init__(self, column_name: str, column_type: ColumnType, labels: list[str]):
        super().__init__(column_name, column_type)
        self._labels = labels
        self._refs = [FieldRef.parse(label) for label in labels]

    def extract(self, obj: object, context) -> object:
        """Resolve the metadata location for each label and see if the label is present."""
        for ref in self._refs:
            if ref.n_parents > 0:
                obj = context.get_parent(obj, ref.n_parents)
            if obj is None:
                fail(f"Missing parent or too many ^ while evaluating {ref.target}")
            if available := obj.get("metadata", {}).get("labels", {}):
                # If the label is present here, return the value here, even if null
                if ref.target in available:
                    return available[ref.target]

    def __str__(self):
        """For debug output"""
        return f"{self.column_name} label={','.join(self._labels)}"


class PathExtractor(Extractor):
    """Extract a column value from the target of a JMESPath expression."""

    def __init__(self, column_name: str, column_type: ColumnType, path: str):
        super().__init__(column_name, column_type)
        self._ref = FieldRef.parse(path)
        self._path = path
        try:
            self._finder = jmespath.compile(self._ref.target)
        except jmespath.exceptions.ParseError as e:
            raise ValueError(f"invalid JMESPath expression {self._ref.target} in column {column_name}") from e

    def extract(self, obj: object, context) -> object:
        """Extract a value from an object using a JMESPath finder."""
        if self._ref.n_parents > 0:
            obj = context.get_parent(obj, self._ref.n_parents)
        if obj is None:
            fail(f"Missing parent or too many ^ while evaluating {self._path}")
        return self._finder.search(obj)

    def __str__(self):
        """For debug output"""
        return f"{self.column_name} path={self._path}"
