"""
NOTE: This is not a good example of how to write user-defined tables.
FIXME: Remove references to non-API imports.
FIXME: Don't use ArgumentParser in the API.
"""

import json
import sys
from argparse import ArgumentParser

import yaml

from kugel.api import domain, table, fail


@domain("stdin")
class Stdin:

    def add_cli_options(self, ap: ArgumentParser):
        # FIXME, artifact of assuming kubernetes
        self.ns = "default"
        pass

    def handle_cli_options(self, args):
        pass

    def get_objects(self, *_):
        text = sys.stdin.read()
        if not text:
            return {}
        if text[0] in "{[":
            return json.loads(text)
        return yaml.safe_load(text)