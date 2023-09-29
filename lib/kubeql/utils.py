import sqlite3
from dataclasses import dataclass

import arrow
import dateutil
from datetime import datetime
from typing import Union

from .jross import from_footprint


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
    mem: float

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
        cpu = Resources.parse_cpu(obj.get("cpu", "0"))
        gpu = int(obj.get("nvidia.com/gpu", 0))
        mem = from_footprint(obj.get("memory", "0"))
        return Resources(cpu, gpu, mem)

    @staticmethod
    def parse_cpu(x: str):
        return float(x[:-1]) / 1000 if "m" in x else float(x)


def add_custom_functions(db):
    """
    Given a SQLite database instance, add pretty_size as a custom function.
    """
    db.create_function("to_size", 1, to_size)
    db.create_function("to_ui", 1, to_ui)


def to_ui(workflow_id: str):
    return workflow_id and f"https://app.mle.pathai.com/jabba/workflows/view/{workflow_id}"


def to_size(nbytes: int):
    """
    Given a byte count, render it as a string in the most appropriate units, suffixed by KB, MB, GB, etc.
    Larger sizes will use the appropriate unit.  The result may have a maximum of one digit after the
    decimal point.
    """
    if nbytes < 1024:
        size, suffix = nbytes, "B"
        return f"{nbytes}B"
    elif nbytes < 1024 ** 2:
        size, suffix = nbytes / 1024, "KB"
    elif nbytes < 1024 ** 3:
        size, suffix = nbytes / 1024 ** 2, "MB"
    elif nbytes < 1024 ** 4:
        size, suffix = nbytes / 1024 ** 3, "GB"
    else:
        size, suffix = nbytes / 1024 ** 4, "TB"
    if size < 10:
        return f"{size:.1f}{suffix}"
    else:
        return f"{round(size)}{suffix}"


def to_age(x: Union[datetime,str]):
    if isinstance(x, str):
        x = dateutil.parse(x)
    return arrow.get() - arrow.get(x)