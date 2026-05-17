"""
Logic to extract column values from YAML fields.
Formerly in ./config.py, refactored for clarity.
"""

from dataclasses import dataclass
import re
from typing import Literal, Optional

import jmespath

from kugl.util import parse_utc, parse_age, parse_size, parse_cpu, abbreviate, fail

ColumnType = Literal["text", "integer", "real", "date", "age", "size", "cpu"]

KUGL_TYPE_CONVERTERS = {
    # Valid choices for column type in config -> function to extract that from a string
    "integer": int,
    "real": float,
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


_SCOPE_PREFIX = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\.(.+)$")


@dataclass
class FieldRef:
    """Parsed form of a potentially-scoped JMESPath expression or label."""

    scope_name: Optional[str]
    target: str

    @classmethod
    def parse(cls, s: str) -> "FieldRef":
        """Parse a path/label string, raising if ^ syntax is used."""
        if "^" in s:
            fail("^ parent navigation is no longer supported; use named row_source scopes instead")
        return cls(None, s)

    @classmethod
    def parse_scoped(cls, s: str, scope_names: set) -> "FieldRef":
        """Parse a path/label string, detecting a scope prefix if it matches a declared scope name.

        Returns FieldRef with scope_name=None if the leading word is not a declared scope,
        leaving the full string as the target.
        """
        if "^" in s:
            fail("^ parent navigation is no longer supported; use named row_source scopes instead")
        m = _SCOPE_PREFIX.match(s)
        if m and m.group(1) in scope_names:
            return cls(m.group(1), m.group(2))
        return cls(None, s)


class Extractor:
    """Base class for JSON field -> column value extractor.  This is a Callable with common
    logic in __call__ and expects subclasses to define self.extract, also __str__ for
    debugging.  __str__ should give the column name and a summary of how the extractor
    is configured."""

    def __init__(self, column_name: str, column_type: ColumnType):
        self.column_name = column_name
        self.column_type = column_type
        self._converter = KUGL_TYPE_CONVERTERS[column_type]

    # FIXME: better contract for context
    def __call__(self, obj: object, context) -> object:
        """Extract the column value from an object and convert to the correct type.  The
        object can be None, implying data missing from the JSON."""
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

    def __init__(self, column_name: str, column_type: ColumnType, labels: list[str],
                 scope_name: Optional[str] = None):
        super().__init__(column_name, column_type)
        for label in labels:
            if "^" in label:
                raise ValueError(
                    f"^ parent navigation is no longer supported in column {column_name}; "
                    f"use named row_source scopes instead"
                )
        self._labels = labels
        self._scope_name = scope_name

    def extract(self, obj: object, context) -> object:
        """Resolve the metadata location for each label and see if the label is present."""
        if self._scope_name:
            obj = context.get_scope(obj, self._scope_name)
            if obj is None:
                fail(f"Unknown scope '{self._scope_name}' for column '{self.column_name}'")
        if available := obj.get("metadata", {}).get("labels", {}):
            for label in self._labels:
                if label in available:
                    return available[label]

    def __str__(self):
        """For debug output"""
        return f"{self.column_name} label={','.join(self._labels)}"


class PathExtractor(Extractor):
    """Extract a column value from the target of a JMESPath expression."""

    def __init__(self, column_name: str, column_type: ColumnType, path: str,
                 scope_name: Optional[str] = None):
        super().__init__(column_name, column_type)
        if "^" in path:
            raise ValueError(
                f"^ parent navigation is no longer supported in column {column_name}; "
                f"use named row_source scopes instead"
            )
        self._scope_name = scope_name
        self._path = path
        try:
            self._finder = jmespath.compile(path)
        except jmespath.exceptions.ParseError as e:
            raise ValueError(
                f"invalid JMESPath expression {path} in column {column_name}"
            ) from e

    def extract(self, obj: object, context) -> object:
        """Extract a value from an object using a JMESPath finder."""
        if self._scope_name:
            obj = context.get_scope(obj, self._scope_name)
            if obj is None:
                fail(f"Unknown scope '{self._scope_name}' for column '{self.column_name}'")
        return self._finder.search(obj)

    def __str__(self):
        """For debug output"""
        return f"{self.column_name} path={self._path}"
