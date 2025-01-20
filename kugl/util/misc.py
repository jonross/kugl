"""
Assorted utility functions / classes with no obvious home.
"""
import json
import re
import subprocess as sp
import sys
from typing import Optional, Union, Callable, Tuple

import arrow

from .debug import debugging

WHITESPACE_RE = re.compile(r"\s+")
TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


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
