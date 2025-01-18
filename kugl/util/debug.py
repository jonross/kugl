import sys
from contextlib import contextmanager
from typing import Union, Optional, Callable

DEBUG_FLAGS = {}

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


