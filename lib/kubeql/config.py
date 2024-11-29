import json
from pathlib import Path
from typing import Literal, Optional, Union, Tuple

from pydantic import BaseModel, NonNegativeInt, ConfigDict, ValidationError

from kubeql.constants import KUBEQL_HOME


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