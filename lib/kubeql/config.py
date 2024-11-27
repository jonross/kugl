from typing import Literal, Optional

from pydantic import BaseModel, NonNegativeInt, ConfigDict


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
