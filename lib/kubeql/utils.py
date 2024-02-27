from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import arrow
import dateutil
from datetime import datetime
import yaml

from .constants import CONFIG
from .jross import from_footprint, to_footprint



class K8SObjectHelper:
    """
    Some common code for wrappers on JSON for pods, nodes et cetera
    """

    def __init__(self, obj):
        self.obj = obj
        self.metadata = self.obj.get("metadata", {})
        self.labels = self.metadata.get("labels", {})

    def __getitem__(self, key):
        """Return a key from the object; no default, will error if not present"""
        return self.obj[key]

    @property
    def name(self):
        """Return the name of the object from the metadata, or none if unavailable."""
        return self.metadata.get("name") or self.obj.get("name")

    @property
    def namespace(self):
        """Return the name of the object from the metadata, or none if unavailable."""
        return self.metadata.get("namespace")

    def label(self, name):
        """
        Return one of the labels from the object, or None if it doesn't have that label.
        """
        return self.labels.get(name)


@dataclass
class Resources:
    cpu: float
    gpu: float
    mem: int

    def __add__(self, other):
        return Resources(self.cpu + other.cpu, self.gpu + other.gpu, self.mem + other.mem)

    def __radd__(self, other):
        """Needed to support sum()"""
        return self if other == 0 else self.__add__(other)

    def as_tuple(self):
        return (self.cpu, self.gpu, self.mem)

    @classmethod
    def extract(cls, obj):
        if obj is None:
            return Resources(0, 0, 0)
        cpu = from_footprint(obj.get("cpu", "0"))
        gpu = int(obj.get("nvidia.com/gpu", 0))
        mem = from_footprint(obj.get("memory", "0"))
        return Resources(cpu, gpu, mem)


def add_custom_functions(db):
    """
    Given a SQLite database instance, add pretty_size as a custom function.
    """
    db.create_function("to_size", 1, to_footprint)
    db.create_function("to_ui", 1, to_ui)


def to_ui(workflow_id: str):
    return workflow_id and f"https://app.mle.pathai.com/jabba/workflows/view/{workflow_id}"


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

    def extra_columns(self, table_name: str) -> dict:
        return self.data.get("columns", {}).get(table_name, {})
