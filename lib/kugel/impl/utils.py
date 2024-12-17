
import os
from pathlib import Path

from kugel.model.config import KPath

from kugel.model.age import Age
from kugel.impl.time import to_utc
from .jross import to_footprint
import kugel.impl.time as ktime

DEBUG_FLAGS = {}


def kugel_home() -> KPath:
    if "KUGEL_HOME" in os.environ:
        return KPath(os.environ["KUGEL_HOME"])
    return KPath.home() / ".kugel"


def kube_home() -> KPath:
    if "KUGEL_HOME" in os.environ:
        return KPath(os.environ["KUGEL_HOME"]) / ".kube"
    return KPath.home() / ".kube"


def debug(features: list[str], on: bool = True):
    """Turn debugging on or off for a set of features.

    :param features: list of feature names, parsed from the --debug command line option;
        "all" means everything.
    """
    for feature in features:
        if feature == "all" and not on:
            DEBUG_FLAGS.clear()
        else:
            DEBUG_FLAGS[feature] = on


def debugging(feature: str = None) -> bool:
    """Check if a feature is being debugged."""
    if feature is None:
        return len(DEBUG_FLAGS) > 0
    return DEBUG_FLAGS.get(feature) or DEBUG_FLAGS.get("all")


def dprint(feature, *args, **kwargs):
    """Print a debug message if the given feature is being debugged."""
    if debugging(feature):
        print(*args, **kwargs)


def add_custom_functions(db):
    db.create_function("to_size", 1, to_footprint)
    db.create_function("now", 0, lambda: ktime.CLOCK.now())
    db.create_function("to_age", 1, lambda x: Age(x - ktime.CLOCK.now()).render())
    db.create_function("to_utc", 1, lambda x: to_utc(x))


def fail(message: str):
    raise KugelError(message)


class KugelError(Exception):
    pass
