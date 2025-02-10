from functools import cache
import json
import os
from pathlib import Path
from typing import Literal, Optional

import yaml

from .age import Age
from .debug import debugging
from .misc import best_guess_parse, fail
from ..util import clock as clock


class KPath(type(Path())):
    """It would be nice if Path were smarter, so do that."""

    def is_world_writeable(self) -> bool:
        return self.stat().st_mode & 0o2 == 0o2

    def parse(self, hint: Optional[Literal["json", "yaml"]] = None):
        """Attempt to parse a file base on its extension or the supplied hint."""
        content = self.read_text()
        if hint == "json" or (hint is None and self.suffix == ".json"):
            return json.loads(content)
        if hint == "yaml" or (hint is None and self.suffix == ".yaml"):
            return yaml.safe_load(content)
        return best_guess_parse(content)

    def set_age(self, age: Age):
        time = clock.CLOCK.now() - age.value
        os.utime(str(self), times=(time, time))

    def prep(self):
        super().mkdir(parents=True, exist_ok=True)
        return self


class ConfigPath(KPath):
    """Same as a KPath but adds debug statements"""

    def parse(self, *args, **kwargs):
        if debug := debugging("config"):
            debug(f"loading {self}")
        return super().parse(*args, **kwargs)


def kugl_home() -> KPath:
    # KUGL_HOME override is for unit tests, not users
    if "KUGL_HOME" in os.environ:
        return KPath(os.environ["KUGL_HOME"])
    return KPath.home() / ".kugl"


def kugl_cache() -> KPath:
    # KUGL_CACHE override is for unit tests, not users
    if "KUGL_CACHE" in os.environ:
        return KPath(os.environ["KUGL_CACHE"])
    return KPath.home() / ".kuglcache"


def kube_home() -> KPath:
    # KUGL_KUBE_HOME override is for unit tests, not for users (as least for now)
    if "KUGL_KUBE_HOME" in os.environ:
        return KPath(os.environ["KUGL_KUBE_HOME"])
    return KPath.home() / ".kube"


@cache
def kube_context() -> str:
    """Return the current kubernetes context."""
    kube_config = kube_home() / "config"
    if not kube_config.exists():
        fail(f"Missing {kube_config}, can't determine current context")
    current_context = (yaml.safe_load(kube_config.read_text()) or {}).get("current-context")
    if not current_context:
        fail("No current context, please run kubectl config use-context ...")
    return current_context
