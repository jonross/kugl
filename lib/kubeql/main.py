import os
from argparse import ArgumentParser
import sys
from typing import List

from .constants import ALWAYS, CHECK, NEVER
from .engine import Engine
from .utils import KubeConfig, fail, MyConfig


def main(argv: List[str]):
    ap = ArgumentParser()
    ap.add_argument("-n", "--no_update", default=False, action="store_true")
    ap.add_argument("-u", "--update", default=False, action="store_true")
    ap.add_argument("-v", "--verbose", default=False, action="store_true")
    ap.add_argument("sql")
    args = ap.parse_args(argv)
    try:
        main2(args)
    except Exception as e:
        if args.verbose or os.getenv("KUBEQL_NEVER_EXIT") == "true":
            raise
        print(e, file=sys.stderr)
        sys.exit(1)


def main2(args):
    if args.update and args.no_update:
        fail("Cannot specify both --no-update and --update")
    config = MyConfig()
    engine = Engine(config, KubeConfig().current_context(),
                    ALWAYS if args.update else NEVER if args.no_update else CHECK)
    if " " not in args.sql:
        args.sql = config.canned_query(args.sql)
    print(engine.query_and_format(args.sql))