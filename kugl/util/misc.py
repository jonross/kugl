"""
Assorted utility functions / classes with no obvious home.
"""
import json
import os
import re
import subprocess as sp
import sys
from pathlib import Path
from typing import Optional, Union

import arrow
import yaml

from kugl.util import Age, clock

WHITESPACE = re.compile(r"\s+")
DEBUG_FLAGS = {}


def run(args: Union[str, list[str]], error_ok=False):
    """
    Invoke an external command, which may be a list or a string; in the latter case it will be
    interpreted using bash -c.  Returns exit status, stdout and stderr.
    """
    if isinstance(args, str):
        args = ["bash", "-c", args]
    dprint("fetch", f"Running {' '.join(args)}")
    p = sp.run(args, stdout=sp.PIPE, stderr=sp.PIPE, encoding="utf-8")
    if p.returncode != 0 and not error_ok:
        print(f"Failed to run [{' '.join(args)}]:", file=sys.stderr)
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
        dprint("config", f"Loading {self}")
        return super().parse_json()

    def parse_yaml(self):
        dprint("config", f"Loading {self}")
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