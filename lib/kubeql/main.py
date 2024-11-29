import os
from argparse import ArgumentParser
import sys
from typing import List

from .constants import CHECK, ALL_NAMESPACE, NEVER_UPDATE, ALWAYS_UPDATE
from .engine import Engine, Query
from .utils import KubeConfig, fail, MyConfig, set_verbosity


def main(argv: List[str]):
    ap = ArgumentParser()
    ap.add_argument("-a", "--all-namespaces", default=False, action="store_true")
    ap.add_argument("-c", "--cache", default=False, action="store_true")
    ap.add_argument("-n", "--namespace", type=str)
    ap.add_argument("-r", "--reckless", default=False, action="store_true")
    ap.add_argument("-u", "--update", default=False, action="store_true")
    ap.add_argument("-v", "--verbose", default=False, action="store_true")
    ap.add_argument("sql")
    args = ap.parse_args(argv)
    set_verbosity(1 if args.verbose else 0)
    try:
        if args.cache and args.update:
            fail("Cannot use both --cache and --update")
        cache_flag = ALWAYS_UPDATE if args.update else NEVER_UPDATE if args.cache else CHECK
        if args.all_namespaces and args.namespace:
            fail("Cannot use both --all-namespaces and --namespace")
        namespace = ALL_NAMESPACE if args.all_namespaces else args.namespace or "default"
        config = MyConfig()
        engine = Engine(config, KubeConfig().current_context())
        if " " not in args.sql:
            args.sql = config.canned_query(args.sql)
        print(engine.query_and_format(Query(args.sql, namespace, cache_flag, args.reckless)))
    except Exception as e:
        if args.verbose or os.getenv("KUBEQL_NEVER_EXIT") == "true":
            raise
        print(e, file=sys.stderr)
        sys.exit(1)