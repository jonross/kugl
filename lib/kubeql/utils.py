from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import arrow
import dateutil
from datetime import datetime
import yaml

from .constants import CONFIG
from .jross import to_footprint


def add_custom_functions(db):
    """
    Given a SQLite database instance, add pretty_size as a custom function.
    """
    db.create_function("to_size", 1, to_footprint)


def to_age(x: Union[datetime,str]):
    if isinstance(x, str):
        x = dateutil.parse(x)
    return arrow.get() - arrow.get(x)


def fail(message: str):
    class KubeQLError(Exception):
        pass
    raise KubeQLError(message)


def rcfail(message: str):
    fail(f"In .kubeqlrc: {message}")


class KubeConfig:
    """
    A helper class for reading data from .kube/config
    """

    def __init__(self, path: Path = Path.home() / ".kube/config") -> None:
        self._config = yaml.safe_load(path.read_text())

    def current_context(self) -> Optional[str]:
        return self._config.get("current-context")


class MyConfig:

    def __init__(self, content: Union[str, Path] = CONFIG):
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

    def extra_columns(self, table_name: str) -> dict:
        return self.data.get("columns", {}).get(table_name, {})
