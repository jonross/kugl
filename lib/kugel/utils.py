import os
from pathlib import Path
from typing import Union

import arrow
import dateutil
from datetime import datetime

from .jross import to_footprint

DEBUG_FLAGS = {}


def kugel_home() -> Path:
    if "KUGEL_HOME" in os.environ:
        return Path(os.environ["KUGEL_HOME"])
    return Path.home() / ".kugel"


def kube_home() -> Path:
    if "KUGEL_HOME" in os.environ:
        return Path(os.environ["KUGEL_HOME"]) / ".kube"
    return Path.home() / ".kube"


def debug(features: list[str], on: bool = True):
    for feature in features:
        DEBUG_FLAGS[feature] = on


def dprint(feature, *args, **kwargs):
    if DEBUG_FLAGS.get(feature):
        print(*args, **kwargs)


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
    raise KugelError(message)


class KugelError(Exception):
    pass