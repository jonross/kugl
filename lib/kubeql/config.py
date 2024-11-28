import json
from typing import Literal, Optional, Union

from pydantic import BaseModel, NonNegativeInt, ConfigDict, ValidationError


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_namespace: str = "default"
    cache_timeout: NonNegativeInt = 120
    reckless: bool = False


class ColumnDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["str", "int", "float"]
    source: str


class ExtendTable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: dict[str, ColumnDef]


class CreateTable(ExtendTable):
    resource: str
    namespaced: bool


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: Optional[Settings] = Settings()
    extend: dict[str, ExtendTable] = {}
    create: dict[str, CreateTable] = {}
    canned: dict[str, str] = {}


def validate_config(root) -> Union[Config, list[str]]:
    """
    Validated the config file structure and contents.  Returns the validated config or a list
    of Pydantic errors as strings.
    """
    try:
        return Config.parse_obj(root)
    except ValidationError as e:
        return [f"{'.'.join(x['loc'])}: {x['msg']}" for x in e.errors()]