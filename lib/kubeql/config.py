
from dataclasses import dataclass
from pathlib import Path

import jmespath
import yaml

from .column import KColumn
from .constants import CONFIG
from .utils import fail, rcfail


class KConfig:

    def __init__(self, content: str | Path = CONFIG):
        """
        Create a utility wrapper around the KubeQL configuration file.
        :param content str|Path: The content of the configuration file, or a path to it.
        :raises Exception: Anything that can be raised by the built-in open() function or
            by yaml.safe_load()
        """
        if isinstance(content, Path):
            content = content.read_text()
        self.data = yaml.safe_load(content)

    def canned_query(self, name: str) -> str:
        """
        Return the canned query with the given name.
        :raises KeyError: If the query does not exist
        """
        kql = self.data.get("canned", {}).get(name)
        if kql is None:
            rcfail(f"No canned query named '{name}'")
        return kql

    def extra_columns(self, table_name: str) -> list[KColumn]:
        extras = self.data.get("columns", {}).get(table_name, {})
        return [KColumn.from_config(k, table_name, v) for k, v in extras.items()]