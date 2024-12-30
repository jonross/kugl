"""
Use this for queries that don't reference any tables.

NOTE: This is not a good example of how to write user-defined tables.
FIXME: Remove references to non-API imports.
FIXME: Don't use ArgumentParser in the API.
"""

from argparse import ArgumentParser

from kugl.api import domain


@domain("empty")
class Empty:

    def add_cli_options(self, ap: ArgumentParser):
        # FIXME, artifact of assuming kubernetes
        self.namespace = "default"
        pass

    def handle_cli_options(self, args):
        pass

    def get_objects(self, *_):
        return {}