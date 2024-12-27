"""
Pydantic models for configuration files.
"""

import re
from typing import Literal, Optional, Tuple, Callable, Union

import funcy as fn
import jmespath
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.functional_validators import model_validator

from kugel.util import Age, parse_utc, parse_size, KPath, ConfigPath, parse_age, parse_cpu, fail

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
    _extract: Callable[[object], object]
    _parents: int
    _sqltype: str
    _convert: type

    @model_validator(mode="after")
    @classmethod
    def gen_extractor(cls, config: 'ColumnDef') -> 'ColumnDef':
        """
        Generate the extract function for a column definition; given an object, it will
        return a coluumn value of the appropriate type.
        """
        if config.path and config.label:
            raise ValueError("cannot specify both path and label")
        elif config.path:
            config._extract = cls._gen_jmespath_extractor(config)
        elif config.label:
            config._extract = cls._gen_label_extractor(config)
        else:
            raise ValueError("must specify either path or label")
        config._sqltype = KUGEL_TYPE_TO_SQL_TYPE[config.type]
        config._convert = KUGEL_TYPE_CONVERTERS[config.type]
        return config

    def extract(self, obj: object) -> object:
        """Extract the column value from an object."""
        if obj is None:
            return None
        value = self._extract(obj)
        return None if value is None else self._convert(value)

    @classmethod
    def _gen_jmespath_extractor(cls, config: 'ColumnDef') -> Callable[[object], object]:
        """Generate a JMESPath extractor function for a column definition."""
        m = PARENTED_PATH.match(config.path)
        parents = len(m.group(1))
        try:
            finder = jmespath.compile(m.group(2))
        except jmespath.exceptions.ParseError as e:
            raise ValueError(f"invalid JMESPath expression {m.group(2)} in column {config.name}") from e
        return lambda obj: cls._extract_jmespath(obj, finder, parents)

    @classmethod
    def _extract_jmespath(cls, obj: object, finder: jmespath.parser.Parser, parents: int) -> object:
        """Extract a value from an object using a JMESPath finder."""
        count = 0
        while count < parents and obj is not None:
            obj = obj.get("__parent")
            count += 1
        return  None if obj is None else finder.search(obj)

    @classmethod
    def _gen_label_extractor(cls, config: 'ColumnDef') -> Callable[[object], object]:
        """Generate a label extractor function for a column definition."""
        labels = config.label if isinstance(config.label, list) else [config.label]
        return lambda obj: cls._extract_label(obj, labels)

    @classmethod
    def _extract_label(cls, obj: object, labels: list[str]) -> object:
        """Extract a value from an object using a label."""
        while (parent := obj.get("__parent")) is not None:
            obj = parent
        available = obj.get("metadata", {}).get("labels", {})
        for label in labels:
            if (value := available.get(label)) is not None:
                return value


KUGEL_TYPE_CONVERTERS = {
    "integer": int,
    "real" : float,
    "text": str,
    "date": parse_utc,
    "age": parse_age,
    "size": parse_size,
    "cpu": parse_cpu,
}

KUGEL_TYPE_TO_SQL_TYPE = {
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
    namespaced: bool = True


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


class Config(BaseModel):
    """The actual configuration model used by the rest of Kugel."""
    settings: Settings
    resources: dict[str, ResourceDef]
    extend: dict[str, ExtendTable]
    create: dict[str, CreateTable]
    shortcuts: dict[str, list[str]]

    @classmethod
    def collate(cls, user_init: UserInit, user_config: UserConfig) -> 'Config':
        """Turn a UserConfig into a more convenient form."""
        config = Config(
            settings=user_init.settings,
            resources={r.name: r for r in user_config.resources},
            extend={e.table: e for e in user_config.extend},
            create={c.table: c for c in user_config.create},
            shortcuts=user_init.shortcuts,
        )
        for table in config.create.values():
            if table.resource not in config.resources:
                fail(f"Table '{table.table}' needs unknown resource '{table.resource}'")
        return config


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

