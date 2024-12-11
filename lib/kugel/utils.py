import os
from pathlib import Path

from .jross import to_footprint
from .time import Age, epoch_to_utc
import kugel.time as ktime

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


def debugging(feature: str = None) -> bool:
    if feature is None:
        return len(DEBUG_FLAGS) > 0
    return DEBUG_FLAGS.get(feature) or DEBUG_FLAGS.get("all")


def dprint(feature, *args, **kwargs):
    if debugging(feature):
        print(*args, **kwargs)


def add_custom_functions(db):
    """
    Given a SQLite database instance, add pretty_size as a custom function.
    """
    db.create_function("to_size", 1, to_footprint)
    db.create_function("now", 0, lambda: ktime.CLOCK.now())
    db.create_function("to_age", 1, lambda x: Age(x - ktime.CLOCK.now()).render())
    db.create_function("to_utc", 1, lambda x: epoch_to_utc(x))


def fail(message: str):
    raise KugelError(message)


class KugelError(Exception):
    pass