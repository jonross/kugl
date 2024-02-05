from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional, Union

import arrow
import dateutil
from datetime import datetime
import yaml

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


class KubeConfig:
    """
    A helper class for reading data from .kube/config
    """

    def __init__(self, path: Path = Path.home() / ".kube/config") -> None:
        self._config = yaml.safe_load(path.read_text())

    def current_context(self) -> Optional[str]:
        return self._config.get("current-context")
