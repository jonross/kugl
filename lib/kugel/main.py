import os
from argparse import ArgumentParser
import sys
from pathlib import Path
from typing import List

import yaml

from .config import validate_config, Config
from .constants import CHECK, ALL_NAMESPACE, NEVER_UPDATE, ALWAYS_UPDATE, KUGEL_HOME
from .engine import Engine, Query
from .utils import fail, set_verbosity


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
            fail("Cannot use both -c/--cache and -u/--update")
        cache_flag = ALWAYS_UPDATE if args.update else NEVER_UPDATE if args.cache else CHECK

        if args.all_namespaces and args.namespace:
            fail("Cannot use both -a/--all-namespaces and -n/--namespace")
        namespace = ALL_NAMESPACE if args.all_namespaces else args.namespace or "default"

        kube_config = Path.home() / ".kube" / "config"
        if not kube_config.exists():
            fail(f"Missing {kube_config}, can't determine current context")

        current_context = yaml.safe_load(kube_config.read_text()).get("current-context")
        if not current_context:
            fail("No current context, please run kubectl config use-context ...")

        KUGEL_HOME.mkdir(exist_ok=True)
        init_file = KUGEL_HOME / "init.yaml"
        if init_file.exists():
            config, errors = validate_config(yaml.safe_load(init_file.read_text()))
            if errors:
                fail("\n".join(errors))
        else:
            config = Config({})

        if " " in args.sql:
            query = args.sql
        elif not (query := config.canned.get(args.sql)):
            fail(f"No canned query named '{args.sql}'")

        engine = Engine(config, current_context)
        print(engine.query_and_format(Query(query, namespace, cache_flag, args.reckless)))

    except Exception as e:
        if args.verbose or os.getenv("KUGEL_NEVER_EXIT") == "true":
            raise
        print(e, file=sys.stderr)
        sys.exit(1)