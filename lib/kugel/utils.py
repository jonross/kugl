import os
import re
from pathlib import Path
from typing import Union, Dict

import arrow
import datetime as dt
import dateutil

from .jross import to_footprint

DEBUG_FLAGS = {}


class Age(dt.timedelta):
    """
    A specialization of timedelta that handles age strings like "10s", "5m30s", "1h", "2d12h".
    """

    AGE_RE = re.compile(r"(\d+[a-z])+")
    AGE_PART = re.compile(r"\d+[a-z]")

    def __new__(cls, *args, **kwargs):
        """
        Create a new Age object.  Parameters may be one of
        - a string like "10s", "5m30s", "1h", "2d12h"
        - an integer number of seconds
        - kwargs to pass to timedelta
        """
        if args:
            if kwargs:
                raise ValueError("Cannot specify both positional and keyword arguments")
            if len(args) > 1:
                raise ValueError("Too many positional arguments")
            arg = args[0]
            if isinstance(arg, str):
                return super().__new__(cls, **Age.parse(arg))
            elif isinstance(arg, int) or isinstance(arg, float):
                return super().__new__(cls, seconds=arg)
            else:
                raise ValueError(f"Invalid argument type: {arg}, {type(arg)}")
        elif not kwargs:
            raise ValueError("Must specify positional or keyword arguments")
        else:
            return super().__new__(cls, **kwargs)

    @classmethod
    def parse(cls, x: str) -> Dict[str, int]:
        """
        Convert a string like "10s", "5m30s", "1h", "2d12h" to Python timedelta dict, using suffixes to
        mean s = seconds, m = minutes, h = hours, d = days.
        """
        x = x.strip()
        if not x:
            raise ValueError("Empty argument")
        if not cls.AGE_RE.match(x):
            raise ValueError(f"Invalid age syntax: {x}")
        suffixes = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
        def _parse(part):
            amount, unit = int(part[:-1]), part[-1]
            if unit not in suffixes:
                raise ValueError(f"Invalid suffix {unit}, must be one of [dhms]")
            return (suffixes[unit], amount)
        return dict(_parse(part) for part in cls.AGE_PART.findall(x))

    def render(self):
        """
        Render the age as a string like "10s", "5m30s", "1h", "2d12h".
        """
        if self.days > 9:
            return f"{self.days}d"
        hours = self.seconds // 3600
        if self.days > 0:
            return f"{self.days}d{hours}h" if hours else f"{self.days}d"
        if hours > 9:
            return f"{hours}h"
        minutes = (self.seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h{minutes}m" if minutes else f"{hours}h"
        if minutes > 9:
            return f"{minutes}m"
        seconds = int(self.seconds % 60)
        if minutes > 0:
            return f"{minutes}m{seconds}s" if seconds else f"{minutes}m"
        return f"{seconds}s"


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


def to_age(x: Union[dt.datetime,str]):
    if isinstance(x, str):
        x = dateutil.parse(x)
    return arrow.get() - arrow.get(x)


def fail(message: str):
    raise KugelError(message)


class KugelError(Exception):
    pass