"""
NOTE: This is not a good example of how to write user-defined tables.
FIXME: Remove references to non-API imports.
FIXME: Don't use ArgumentParser in the API.
"""

import json
import sys
from argparse import ArgumentParser

from kugel.api import domain, table, fail


@domain("stdin")
class Stdin:

    def add_cli_options(self, ap: ArgumentParser):
        pass

    def handle_cli_options(self, args):
        pass

    def get_objects(self, *_):
        return json.loads(sys.stdin.read())