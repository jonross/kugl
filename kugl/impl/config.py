"""
Pydantic models for configuration files.
"""
import json
import re
from typing import Literal, Optional, Tuple, Callable, Union

import jmespath
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.functional_validators import model_validator

from kugl.util import Age, parse_utc, parse_size, KPath, ConfigPath, parse_age, parse_cpu, fail

PARENTED_PATH = re.compile(r"^(\^*)(.*)")
DEFAULT_SCHEMA = "kubernetes"

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


class Settings(BaseModel):
    """Holds the settings: entry from a user config file."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    cache_timeout: Age = Age(120)
    reckless: bool = False


class UserInit(BaseModel):
    """The root model for init.yaml; holds the entire file content."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    settings: Optional[Settings] = Settings()
    shortcuts: dict[str, list[str]] = {}


class Column(BaseModel):
    """The minimal field set for a table column defined from code.  Columns defined from user
    config files use UserColumn, a subclass."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    name: str
    type: Literal["text", "integer", "real", "date", "age", "size", "cpu"] = "text"
    comment: Optional[str] = None
    # SQL type for this column
    _sqltype: str

    @model_validator(mode="after")
    @classmethod
    def recognize_type(cls, column: 'Column') -> 'Column':
        column._sqltype = KUGL_TYPE_TO_SQL_TYPE[column.type]
        return column


class UserColumn(Column):
    """Holds one entry from a columns: list in a user config file."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    path: Optional[str] = None
    label: Optional[Union[str, list[str]]] = None
    # Parsed value of self.path
    _finder: jmespath.parser.Parser
    # Number of ^ in self.path
    _parents: int
    # Function to extract a column value from an object.
    _extract: Callable[[object], object]
    # Function to convert the extracted value to the SQL type
    _convert: type

    @model_validator(mode="after")
    @classmethod
    def gen_extractor(cls, column: 'UserColumn') -> 'UserColumn':
        """
        Generate the extract function for a column definition; given an object, it will
        return a column value of the appropriate type.
        """
        if column.path and column.label:
            raise ValueError("cannot specify both path and label")
        elif column.path:
            m = PARENTED_PATH.match(column.path)
            column._parents = len(m.group(1))
            try:
                column._finder = jmespath.compile(m.group(2))
            except jmespath.exceptions.ParseError as e:
                raise ValueError(f"invalid JMESPath expression {m.group(2)} in column {column.name}") from e
            column._extract = column._extract_jmespath
        elif column.label:
            if not isinstance(column.label, list):
                column.label = [column.label]
            column._extract = column._extract_label
        else:
            raise ValueError("must specify either path or label")
        column._convert = KUGL_TYPE_CONVERTERS[column.type]
        return column

    def extract(self, obj: object, context) -> object:
        """Extract the column value from an object and convert to the correct type."""
        if obj is None:
            if context.debug:
                context.debug(f"no object provided to extractor {self}")
            return None
        if context.debug:
            context.debug(f"get {self} from {self._abbreviate(obj)}")
        value = self._extract(obj, context)
        result = None if value is None else self._convert(value)
        if context.debug:
            context.debug(f"got {result}")
        return result

    def _extract_jmespath(self, obj: object, context) -> object:
        """Extract a value from an object using a JMESPath finder."""
        if self._parents > 0:
            obj = context.get_parent(obj, self._parents)
        if obj is None:
            fail(f"Missing parent or too many ^ while evaluating {self.path}")
        return self._finder.search(obj)

    def _extract_label(self, obj: object, context) -> object:
        """Extract a value from an object using a label."""
        obj = context.get_root(obj)
        if available := obj.get("metadata", {}).get("labels", {}):
            for label in self.label:
                if (value := available.get(label)) is not None:
                    return value

    def __str__(self):
        if self.path:
            return f"{self.name} path={self.path}"
        return f"{self.name} label={','.join(self.label)}"

    def _abbreviate(self, obj):
        text = json.dumps(obj)
        if len(text) > 100:
            return text[:100] + "..."
        return text


class ExtendTable(BaseModel):
    """Holds the extend: section from a user config file."""
    model_config = ConfigDict(extra="forbid")
    table: str
    columns: list[UserColumn] = []


class ResourceDef(BaseModel):
    """Holds one entry from the resources: list in a user config file.

    This only ensures the .name and .cacheable attributes are properly typed.  The remaining
    validation happens in registry.py when we create a (possibly) schema-specific Resource.
    """
    model_config = ConfigDict(extra="allow")
    name: str
    cacheable: Optional[bool] = None


class CreateTable(ExtendTable):
    """Holds the create: section from a user config file."""
    resource: str
    row_source: Optional[list[str]] = None


class UserConfig(BaseModel):
    """The root model for a user config file; holds the complete file content."""
    model_config = ConfigDict(extra="forbid")
    resources: list[ResourceDef] = []
    extend: list[ExtendTable] = []
    create: list[CreateTable] = []
    # User can put chunks of reusable YAML under here, we will ignore
    utils: Optional[object] = None


# FIXME use typevars
def parse_model(model_class, root: dict) -> Tuple[object, list[str]]:
    """Parse a dict into a model instance (typically a UserConfig).

    :return: A tuple of (parsed object, list of errors).  On success, the error list is None.
        On failure, the parsed object is None.
    """
    try:
        return model_class.model_validate(root), None
    except ValidationError as e:
        error_location = lambda err: '.'.join(str(x) for x in err['loc'])
        return None, [f"{error_location(err)}: {err['msg']}" for err in e.errors()]

# FIXME use typevars
def parse_file(model_class, path: ConfigPath) -> Tuple[object, list[str]]:
    """Parse a configuration file into a model instance, handling edge cases.

    :return: Same as parse_model."""
    if not path.exists():
        return model_class(), None
    if path.is_world_writeable():
        return None, [f"{path} is world writeable, refusing to run"]
    return parse_model(model_class, path.parse_yaml() or {})

