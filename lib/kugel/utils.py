import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import arrow
import dateutil
from datetime import datetime
import yaml

from .jross import to_footprint

VERBOSITY = 0


def kugel_home() -> Path:
    if "KUGEL_HOME" in os.environ:
        return Path(os.environ["KUGEL_HOME"])
    return Path.home() / ".kugel"


def set_verbosity(v: int):
    global VERBOSITY
    VERBOSITY = v


def vprint(*args, **kwargs):
    if VERBOSITY > 0:
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