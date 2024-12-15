"""
Pydantic models for configuration files.
"""

from typing import Literal, Optional, Union, Tuple, Annotated

import jmespath
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.functional_validators import model_validator

from kugel.model import Age


class Settings(BaseModel):
    """Holds the settings: entry from a user config file."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    cache_timeout: Age = Age(120)
    reckless: bool = False


class ColumnDef(BaseModel):
    """Holds one entry from a columns: list in a user config file."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    type: Literal["str", "int", "float"] = "str"
    path: Optional[str] = None
    label: Optional[str] = None
    _finder: jmespath.parser.Parser
    _sqltype: str
    _pytype: type

    @model_validator(mode="after")
    @classmethod
    def parse_path(cls, config: 'ColumnDef') -> 'ColumnDef':
        if config.path and config.label:
            raise ValueError("cannot specify both path and label")
        if not config.path and not config.label:
            raise ValueError("must specify either path or label")
        if config.label:
            config.path = f"metadata.labels.\"{config.label}\""
        try:
            jmesexpr = jmespath.compile(config.path)
            config._finder = lambda obj: jmesexpr.search(obj)
        except jmespath.exceptions.ParseError as e:
            raise ValueError(f"invalid JMESPath expression {config.path}") from e
        config._sqltype, config._pytype = {
            "str": ("TEXT", str),
            "int": ("INTEGER", int),
            "float": ("REAL", float),
        }[config.type]
        return config

    def extract(self, obj: object) -> object:
        value = self._finder(obj)
        return None if value is None else self._pytype(value)


class ExtendTable(BaseModel):
    """Holds the extend: section from a user config file."""
    model_config = ConfigDict(extra="forbid")
    columns: dict[str, ColumnDef] = {}


class ResourceDef(BaseModel):
    """Holds one entry from the resources: list in a user config file."""
    namespaced: bool  # TODO use this in engine query


class CreateTable(ExtendTable):
    """Holds the create: section from a user config file."""
    resource: str
    builder: str = "kugel.tables.TableBuilder"  # TODO get this via the registry


class Config(BaseModel):
    """The root model for a user config file; holds the complete file content."""
    model_config = ConfigDict(extra="forbid")
    settings: Optional[Settings] = Settings()
    resources: list[ResourceDef] = []
    extend: dict[str, ExtendTable] = {}
    create: dict[str, CreateTable] = {}
    alias: dict[str, list[str]] = {}


# FIXME use typevars
def parse_model(cls, root) -> Tuple[object, list[str]]:
    """Parse a configuration object (typically a Config) from a model.
    :return: A tuple of (parsed object, list of errors).  On success, the error list is None.
        On failure, the parsed object is None.
    """
    try:
        return cls.parse_obj(root), None
    except ValidationError as e:
        return None, [f"{'.'.join(x['loc'])}: {x['msg']}" for x in e.errors()]