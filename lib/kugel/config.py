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
    name: str
    type: Literal["text", "integer", "real"] = "text"
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
        config._sqltype, config._pytype = config.type, dict(text=str, integer=int, real=float)[config.type]
        return config

    def extract(self, obj: object) -> object:
        value = self._finder(obj)
        return None if value is None else self._pytype(value)


class ExtendTable(BaseModel):
    """Holds the extend: section from a user config file."""
    model_config = ConfigDict(extra="forbid")
    table: str
    columns: list[ColumnDef] = []


class ResourceDef(BaseModel):
    """Holds one entry from the resources: list in a user config file."""
    name: str
    namespaced: bool = True  # TODO use this in engine query


class CreateTable(ExtendTable):
    """Holds the create: section from a user config file."""
    resource: str


class UserConfig(BaseModel):
    """The root model for a user config file; holds the complete file content."""
    model_config = ConfigDict(extra="forbid")
    settings: Optional[Settings] = Settings()
    resources: list[ResourceDef] = []
    extend: list[ExtendTable] = []
    create: list[CreateTable] = []
    alias: dict[str, list[str]] = {}


class Config(BaseModel):
    """The actual configuration model used by the rest of Kugel."""
    settings: Settings
    resources: dict[str, ResourceDef]
    extend: dict[str, ExtendTable]
    create: dict[str, CreateTable]
    alias: dict[str, list[str]]

    @classmethod
    def collate(cls, user_config: UserConfig) -> 'Config':
        """Turn a UserConfig into a more convenient form."""
        return Config(
            settings=user_config.settings,
            resources={r.name: r for r in user_config.resources},
            extend={e.table: e for e in user_config.extend},
            create={c.table: c for c in user_config.create},
            alias=user_config.alias,
        )


# FIXME use typevars
def parse_model(cls, root) -> Tuple[object, list[str]]:
    """Parse a configuration object (typically a Config) from a model.
    :return: A tuple of (parsed object, list of errors).  On success, the error list is None.
        On failure, the parsed object is None.
    """
    try:
        return cls.parse_obj(root), None
    except ValidationError as e:
        error_location = lambda err: '.'.join(str(x) for x in err['loc'])
        return None, [f"{error_location(err)}: {err['msg']}" for err in e.errors()]