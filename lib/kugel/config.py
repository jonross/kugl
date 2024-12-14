from typing import Literal, Optional, Union, Tuple, Annotated

import jmespath
from pydantic import BaseModel, Field, NonNegativeInt, ConfigDict, ValidationError, root_validator
from pydantic.functional_validators import model_validator

from kugel.model import Age


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    cache_timeout: Age = Age(120)
    reckless: bool = False


class ColumnDef(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    type: Literal["str", "int", "float"]
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
    model_config = ConfigDict(extra="forbid")
    columns: dict[str, ColumnDef] = {}


EMPTY_EXTENSION = ExtendTable(columns={})


class ResourceDef(BaseModel):
    namespaced: bool  # TODO use this in engine query


class CreateTable(ExtendTable):
    resource: str
    builder: str = "kugel.tables.TableBuilder"  # TODO get this via the registry


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: Optional[Settings] = Settings()
    resources: dict[str, ResourceDef] = {}
    extend: dict[str, ExtendTable] = {}
    create: dict[str, CreateTable] = {}
    alias: dict[str, list[str]] = {}

    # Private fields offering dict indices for the above fields
    _resources: dict[str, ResourceDef]

    @model_validator(mode="after")
    def _build_indices(cls, config: 'Config') -> 'Config':
        config._resources = {name: resource for name, resource in config.resources.items()}
        return config


# FIXME use typevars
def parse_model(cls, root) -> Tuple[object, list[str]]:
    """
    Parse a configuration object (typically a Config) from a model.
    Returns the validated config or a list of Pydantic errors as strings.
    """
    try:
        return cls.parse_obj(root), None
    except ValidationError as e:
        return None, [f"{'.'.join(x['loc'])}: {x['msg']}" for x in e.errors()]