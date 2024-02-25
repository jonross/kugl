from pathlib import Path

import yaml

from .constants import CONFIG
from .utils import fail


class KConfig:

    def __init__(self, path: Path = CONFIG):
        """
        Create a utility wrapper around the KubeQL configuration file.
        :raises Exception: Anything that can be raised by the built-in open() function or
            by yaml.safe_load()
        """
        self.data = yaml.safe_load(path.read_text())

    def canned(self, name: str):
        """
        Return the canned query with the given name.
        :raises KeyError: If the query does not exist
        """
        kql = self.data.get("canned", {}).get(name)
        if kql is None:
            fail(f"No canned query named '{name}'")
        return kql