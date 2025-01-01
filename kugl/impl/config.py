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


class ColumnDef(BaseModel):
    """Holds one entry from a columns: list in a user config file."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    name: str
    type: Literal["text", "integer", "real", "date", "age", "size", "cpu"] = "text"
    path: Optional[str] = None
    label: Optional[Union[str, list[str]]] = None
    # Function to extract a column value from an object.
    _extract: Callable[[object], object]
    # Function to convert the extracted value to the SQL type
    _convert: type
    # Parsed value of self.path
    _finder: jmespath.parser.Parser
    # Number of ^ in self.path
    _parents: int
    # SQL type for this column
    _sqltype: str

    @model_validator(mode="after")
    @classmethod
    def gen_extractor(cls, config: 'ColumnDef') -> 'ColumnDef':
        """
        Generate the extract function for a column definition; given an object, it will
        return a column value of the appropriate type.
        """
        if config.path and config.label:
            raise ValueError("cannot specify both path and label")
        elif config.path:
            m = PARENTED_PATH.match(config.path)
            config._parents = len(m.group(1))
            try:
                config._finder = jmespath.compile(m.group(2))
            except jmespath.exceptions.ParseError as e:
                raise ValueError(f"invalid JMESPath expression {m.group(2)} in column {config.name}") from e
            config._extract = config._extract_jmespath
        elif config.label:
            if not isinstance(config.label, list):
                config.label = [config.label]
            config._extract = config._extract_label
        else:
            raise ValueError("must specify either path or label")
        config._sqltype = KUGL_TYPE_TO_SQL_TYPE[config.type]
        config._convert = KUGL_TYPE_CONVERTERS[config.type]
        return config

    def extract(self, obj: object, context) -> object:
        """Extract the column value from an object and convert to the correct type."""
        if obj is None:
            if context.debug:
                print(f"No object provided to extractor {self}")
            return None
        if context.debug:
            print(f"Extract {self} from {self._abbreviate(obj)}")
        value = self._extract(obj, context)
        if context.debug:
            print(f"Extracted {value}")
        return None if value is None else self._convert(value)

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


KUGL_TYPE_CONVERTERS = {
    "integer": int,
    "real" : float,
    "text": str,
    "date": parse_utc,
    "age": parse_age,
    "size": parse_size,
    "cpu": parse_cpu,
}

KUGL_TYPE_TO_SQL_TYPE = {
    "integer": "integer",
    "real": "real",
    "text": "text",
    "date": "integer",
    "age": "integer",
    "size": "integer",
    "cpu": "real",
}


class ExtendTable(BaseModel):
    """Holds the extend: section from a user config file."""
    model_config = ConfigDict(extra="forbid")
    table: str
    columns: list[ColumnDef] = []


class ResourceDef(BaseModel):
    """Holds one entry from the resources: list in a user config file."""
    name: str
    # FIXME: Don't conflate all resource attributes in one class
    namespaced: bool = True
    cacheable: bool = True
    file: Optional[str] = None
    exec: Optional[Union[str, list[str]]] = None

    @model_validator(mode="after")
    @classmethod
    def validate(cls, config: 'ResourceDef') -> 'ResourceDef':
        if config.file and config.exec:
            raise ValueError("Resource cannot specify both file and exec")
        if config.file:
            config.cacheable = False
        return config

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name


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

