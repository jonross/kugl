from typing import Literal, Optional, Union, Tuple, Annotated

import jmespath
from pydantic import BaseModel, Field, NonNegativeInt, ConfigDict, ValidationError, root_validator
from pydantic.functional_validators import model_validator

from kugel.time import Age


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    cache_timeout: Age = Age(120)
    reckless: bool = False


class ColumnDef(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    type: Literal["str", "int", "float"]
    path: str
    _finder: jmespath.parser.Parser
    _sqltype: str
    _pytype: type

    @model_validator(mode="after")
    @classmethod
    def parse_path(cls, config: 'ColumnDef') -> 'ColumnDef':
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


class ExtendTable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: dict[str, ColumnDef] = {}


EMPTY_EXTENSION = ExtendTable(columns={})


class CreateTable(ExtendTable):
    resource: str
    namespaced: bool  # TODO use this in engine query
    builder: str = "kugel.tables.TableBuilder"


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: Optional[Settings] = Settings()
    extend: dict[str, ExtendTable] = {}
    create: dict[str, CreateTable] = {}
    alias: dict[str, list[str]] = {}


def validate_config(root) -> Tuple[Config, list[str]]:
    """
    Validated the config file structure and contents.  Returns the validated config or a list
    of Pydantic errors as strings.
    """
    try:
        return Config.parse_obj(root), None
    except ValidationError as e:
        return None, [f"{'.'.join(x['loc'])}: {x['msg']}" for x in e.errors()]