import json
from pathlib import Path
from typing import Literal, Optional, Union, Tuple, Annotated

import jmespath
from pydantic import BaseModel, Field, NonNegativeInt, ConfigDict, ValidationError, root_validator
from pydantic.functional_validators import model_validator

from kubeql.constants import KUBEQL_HOME


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_namespace: str = "default"
    cache_timeout: NonNegativeInt = 120
    reckless: bool = False


class ColumnDef(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    type: Literal["str", "int", "float"]
    source: str
    _finder: jmespath.parser.Parser
    _sqltype: str
    _pytype: type

    @model_validator(mode="after")
    @classmethod
    def parse_source(cls, config: 'ColumnDef') -> 'ColumnDef':
        try:
            jmesexpr = jmespath.compile(config.source)
            config._finder = lambda obj: jmesexpr.search(obj)
        except jmespath.exceptions.ParseError as e:
            raise ValueError(f"invalid JMESPath source  for {values['source']}") from e
        config._sqltype, config._pytype = {
            "str": ("TEXT", str),
            "int": ("INTEGER", int),
            "float": ("REAL", float),
        }[config.type]
        return config

    def extract(self, obj):
        value = self._finder(obj)
        return None if value is None else self._pytype(value)


class ExtendTable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: dict[str, ColumnDef]


EMPTY_EXTENSION = ExtendTable(columns={})


class CreateTable(ExtendTable):
    resource: str
    namespaced: bool


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cache_dir: Path = KUBEQL_HOME / "cache"
    settings: Optional[Settings] = Settings()
    extend: dict[str, ExtendTable] = {}
    create: dict[str, CreateTable] = {}
    canned: dict[str, str] = {}


def validate_config(root) -> Tuple[Config, list[str]]:
    """
    Validated the config file structure and contents.  Returns the validated config or a list
    of Pydantic errors as strings.
    """
    try:
        return Config.parse_obj(root), None
    except ValidationError as e:
        return None, [f"{'.'.join(x['loc'])}: {x['msg']}" for x in e.errors()]