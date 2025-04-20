"""
Assorted utility functions / classes with no obvious home.
"""
import json
import re
import subprocess as sp
import sys
from contextlib import contextmanager
from typing import Optional, Union, Callable, Tuple

import arrow
import yaml

from .debug import debugging

WHITESPACE_RE = re.compile(r"\s+")
TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
FAILURE_PREAMBLE = None


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


def parse_utc(utc_str: Optional[str]) -> int:
    return arrow.get(utc_str).int_timestamp if utc_str else None


def to_utc(epoch: int) -> str:
    return arrow.get(epoch).to('utc').format('YYYY-MM-DDTHH:mm:ss') + 'Z'


def warn(message: str):
    print(message, file=sys.stderr)


def fail(message: str, e: Optional[Exception] = None):
    if FAILURE_PREAMBLE is not None:
        message = FAILURE_PREAMBLE + "\n" + message
    if e is not None:
        raise KuglError(message) from e
    raise KuglError(message)


@contextmanager
def failure_preamble(preamble: str):
    """Within this context, all calls to fail() will prepend the preamble to the message."""
    global FAILURE_PREAMBLE
    old_preamble = FAILURE_PREAMBLE
    FAILURE_PREAMBLE = preamble
    try:
        yield
    finally:
        FAILURE_PREAMBLE = old_preamble


class KuglError(Exception):
    pass


def abbreviate(obj):
    if not isinstance(obj, str):
        obj = json.dumps(obj)
    if len(obj) > 100:
        return obj[:100] + "..."
    return obj


def cleave(s: str, sep: str, flip: bool = False):
    if sep in s:
        parts = s.split(sep, 1)
        return parts[0], parts[1]
    return (None, s) if flip else (s, None)


def friendlier_errors(errors: list) -> list[str]:
    """Improve upon Pydantic's error messages."""
    location_str = lambda loc: ".".join(map(str, loc))
    def _improve(error):
        message, location = error['msg'], error['loc']
        if "Extra inputs are not permitted" in message:
            return f"At {location_str(location[:-1])}: '{location[-1]}' is not allowed here"
        return location_str(location) + ": " + message
    return [_improve(e) for e in errors]


def best_guess_parse(text):
    if not text:
        return {}
    if text[0] in "{[":
        return json.loads(text)
    return yaml.safe_load(text)

