import os
from argparse import ArgumentParser
import sys
from typing import List, Optional

import yaml

from .config import validate_config, Config
from .constants import CHECK, ALL_NAMESPACE, NEVER_UPDATE, ALWAYS_UPDATE
from .engine import Engine, Query
from .time import Age
from .utils import fail, debug, kugel_home, kube_home, debugging


def main(argv: List[str], return_config: bool = False) -> Optional[Config]:

    if "KUGEL_UNIT_TESTING" in os.environ and "KUGEL_MOCKDIR" not in os.environ:
        # Never enter main in tests unless test_home fixture is in use, else we could read
        # the user's init file.
        sys.exit("Unit test state error")

    try:
        return _main(argv, return_config=return_config)
    except Exception as e:
        if debugging() or "KUGEL_UNIT_TESTING" in os.environ:
            raise
        print(e, file=sys.stderr)
        sys.exit(1)


def _main(argv: List[str], return_config: bool = False) -> Optional[Config]:

    kugel_home().mkdir(exist_ok=True)
    init_file = kugel_home() / "init.yaml"
    if not init_file.exists():
        config = Config()
    elif init_file.is_world_writeable():
        fail(f"{init_file} is world writeable, refusing to run")
    else:
        config, errors = validate_config(yaml.safe_load(init_file.read_text()) or {})
        if errors:
            fail("\n".join(errors))

    if len(argv) == 1 and " " not in argv[0]:
        if not (new_argv := config.alias.get(argv[0])):
            fail(f"No alias named '{argv[0]}'")
        argv = new_argv

    ap = ArgumentParser()
    ap.add_argument("-a", "--all-namespaces", default=False, action="store_true")
    ap.add_argument("-D", "--debug", type=str)
    ap.add_argument("-c", "--cache", default=False, action="store_true")
    ap.add_argument("-n", "--namespace", type=str)
    ap.add_argument("-r", "--reckless", default=False, action="store_true")
    ap.add_argument("-t", "--timeout", type=str)
    ap.add_argument("-u", "--update", default=False, action="store_true")
    ap.add_argument("sql")
    args = ap.parse_args(argv)

    if args.debug:
        debug(args.debug.split(","))

    if args.cache and args.update:
        fail("Cannot use both -c/--cache and -u/--update")
    cache_flag = ALWAYS_UPDATE if args.update else NEVER_UPDATE if args.cache else CHECK

    if args.all_namespaces and args.namespace:
        fail("Cannot use both -a/--all-namespaces and -n/--namespace")
    namespace = ALL_NAMESPACE if args.all_namespaces else args.namespace or "default"

    if args.reckless:
        config.settings.reckless = True
    if args.timeout:
        config.settings.cache_timeout = Age(args.timeout)

    if return_config:
        return config

    kube_config = kube_home() / "config"
    if not kube_config.exists():
        fail(f"Missing {kube_config}, can't determine current context")

    current_context = (yaml.safe_load(kube_config.read_text()) or {}).get("current-context")
    if not current_context:
        fail("No current context, please run kubectl config use-context ...")

    engine = Engine(config, current_context)
    print(engine.query_and_format(Query(args.sql, namespace, cache_flag)))
