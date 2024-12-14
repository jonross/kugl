
import collections as co

from pydantic import BaseModel

_REGISTRY: dict[str, dict[str, ...]] = co.defaultdict(lambda: co.defaultdict(dict))

class TableDef(BaseModel):
    name: str
    domain: str
    resource: str

def table(**kwargs):
    def wrap(cls):
        table_def = TableDef(**kwargs)
        _REGISTRY[table_def.domain][table_def.name] = cls
        return cls
    return wrap