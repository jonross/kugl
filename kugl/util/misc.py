"""
Assorted utility functions / classes with no obvious home.
"""
import json
import os
import re
import subprocess as sp
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union, Callable, Tuple

import arrow
import funcy as fn
import yaml

from kugl.util import Age, clock

WHITESPACE = re.compile(r"\s+")
DEBUG_FLAGS = {}


def run(args: Union[str, list[str]], error_ok: bool = False) -> Tuple[int, str, str]:
    """
    Invoke an external command, which may be a list or a string; in the latter case it will be
    interpreted using bash -c.  Returns exit status, stdout and stderr.
    """
    if isinstance(args, str):
        args = ["bash", "-c", args]
    if debug := debugging("fetch"):
        debug(f"running {' '.join(args)}")
    p = sp.run(args, stdout=sp.PIPE, stderr=sp.PIPE, encoding="utf-8")
    if p.returncode != 0 and not error_ok:
        print(f"failed to run [{' '.join(args)}]:", file=sys.stderr)
        print(p.stderr, file=sys.stderr, end="")
        sys.exit(p.returncode)
    return p.returncode, p.stdout, p.stderr


def parse_utc(utc_str: str) -> int:
    return arrow.get(utc_str).int_timestamp


def to_utc(epoch: int) -> str:
    return arrow.get(epoch).to('utc').format('YYYY-MM-DDTHH:mm:ss') + 'Z'


def warn(message: str):
    print(message, file=sys.stderr)


def fail(message: str, e: Optional[Exception] = None):
    if e is not None:
        raise KuglError(message) from e
    raise KuglError(message)


class KuglError(Exception):
    pass


def debug_features(features: Union[str, list[str]], on: bool = True):
    """Turn debugging on or off for a set of features.

    :param features: list of feature names, parsed from the --debug command line option;
        "all" means everything.
    """
    if isinstance(features, str):
        features = features.split(",")
    for feature in features:
        if feature == "all" and not on:
            DEBUG_FLAGS.clear()
        else:
            DEBUG_FLAGS[feature] = on


@contextmanager
def features_debugged(features: Union[str, list[str]], on: bool = True):
    """Like debug_features, but works as a context manager to set them temporarily."""
    old_flags = dict(DEBUG_FLAGS)
    debug_features(features, on)
    try:
        yield
    finally:
        DEBUG_FLAGS.clear()
        DEBUG_FLAGS.update(old_flags)


def debugging(feature: str = None) -> Optional[Callable]:
    """Check if a feature is being debugged.

    :return: A callable to print a message to stderr prefixed by the feature name, or
        None if the feature isn't being debugged."""
    if feature is None:
        if len(DEBUG_FLAGS) > 0:
            return lambda *args: _dprint("all", args)
        return None
    if DEBUG_FLAGS.get(feature) or DEBUG_FLAGS.get("all"):
        return lambda *args: _dprint(feature, args)
    return None


def _dprint(feature, args):
    """Print a debug to stderr tagged with the feature name."""
    print(feature + ":", *args, file=sys.stderr)


class KPath(type(Path())):
    """It would be nice if Path were smarter, so do that."""

    def is_world_writeable(self) -> bool:
        return self.stat().st_mode & 0o2 == 0o2

    def parse_json(self):
        return json.loads(self.read_text())

    def parse_yaml(self):
        return yaml.safe_load(self.read_text())

    def set_age(self, age: Age):
        time = clock.CLOCK.now() - age.value
        os.utime(str(self), times=(time, time))


class ConfigPath(KPath):
    """Same as a KPath but adds debug statements"""

    def parse_json(self):
        if debug := debugging("config"):
            debug(f"loading {self}")
        return super().parse_json()

    def parse_yaml(self):
        if debug := debugging("config"):
            debug(f"loading {self}")
        return super().parse_yaml()


def kugl_home() -> KPath:
    # KUGL_HOME override is for unit tests, not for users (as least for now)
    if "KUGL_HOME" in os.environ:
        return KPath(os.environ["KUGL_HOME"])
    return KPath.home() / ".kugl"


def kube_home() -> KPath:
    # KUGL_HOME override is for unit tests, not for users (as least for now)
    if "KUGL_HOME" in os.environ:
        return KPath(os.environ["KUGL_HOME"]) / ".kube"
    return KPath.home() / ".kube"


@fn.memoize
def kube_context() -> str:
    """Return the current kubernetes context."""
    kube_config = kube_home() / "config"
    if not kube_config.exists():
        fail(f"Missing {kube_config}, can't determine current context")
    current_context = (yaml.safe_load(kube_config.read_text()) or {}).get("current-context")
    if not current_context:
        fail("No current context, please run kubectl config use-context ...")
    return current_context