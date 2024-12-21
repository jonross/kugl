"""
Command-line entry point.
"""

import os
from argparse import ArgumentParser
import sys
from typing import List, Optional, Union

import yaml

from kugel.impl.registry import get_domain
from kugel.impl.engine import Engine, Query, CHECK, NEVER_UPDATE, ALWAYS_UPDATE
from kugel.impl.config import Config, UserConfig, UserInit, parse_file
from kugel.util import Age, fail, debug, debugging, kugel_home, kube_home


def main() -> None:
    main1(sys.argv[1:])


def main1(argv: List[str], return_config: bool = False) -> Optional[Union[UserInit, UserConfig]]:

    if "KUGEL_UNIT_TESTING" in os.environ and "KUGEL_MOCKDIR" not in os.environ:
        # Never enter main in tests unless test_home fixture is in use, else we could read
        # the user's init file.
        sys.exit("Unit test state error")

    try:
        return main2(argv, return_config=return_config)
    except Exception as e:
        if debugging() or "KUGEL_UNIT_TESTING" in os.environ:
            raise
        print(e, file=sys.stderr)
        sys.exit(1)


def main2(argv: List[str], return_config: bool = False) -> Optional[Union[UserInit, UserConfig]]:

    kugel_home().mkdir(exist_ok=True)
    if not argv:
        fail("missing sql query")

    # Load init file.
    init_file = kugel_home() / "init.yaml"
    init, errors = parse_file(UserInit, init_file)
    if errors:
        fail("\n".join(errors))

    # Check for aliases now, because they can include command line options.  But the
    # command line as given also applies.  So we have to treat the last arg as SQL or
    # alias name, even before we see the options.
    if " " not in argv[-1]:
        if not (new_argv := init.alias.get(argv[-1])):
            fail(f"No alias named '{argv[-1]}'")
        return main1(argv[:-1] + new_argv)

    # Load config file
    config_file = kugel_home() / "kubernetes.yaml"
    config, errors = parse_file(UserConfig, config_file)
    if errors:
        fail("\n".join(errors))

    domain = get_domain("kubernetes")
    ap = ArgumentParser()
    domain.impl.add_cli_options(ap)
    ap.add_argument("-D", "--debug", type=str)
    ap.add_argument("-c", "--cache", default=False, action="store_true")
    ap.add_argument("-r", "--reckless", default=False, action="store_true")
    ap.add_argument("-t", "--timeout", type=str)
    ap.add_argument("-u", "--update", default=False, action="store_true")
    ap.add_argument("sql")
    args = ap.parse_args(argv)

    domain.impl.handle_cli_options(args)
    cache_flag = ALWAYS_UPDATE if args.update else NEVER_UPDATE if args.cache else CHECK
    if args.debug:
        debug(args.debug.split(","))
    if args.reckless:
        init.settings.reckless = True
    if args.timeout:
        init.settings.cache_timeout = Age(args.timeout)

    # FIXME: this is silly, factor out a function to assist config edge case testing.
    if return_config:
        return init, config
    config = Config.collate(init, config)

    kube_config = kube_home() / "config"
    if not kube_config.exists():
        fail(f"Missing {kube_config}, can't determine current context")

    current_context = (yaml.safe_load(kube_config.read_text()) or {}).get("current-context")
    if not current_context:
        fail("No current context, please run kubectl config use-context ...")

    engine = Engine(config, current_context)
    # FIXME bad reference to namespace
    print(engine.query_and_format(Query(args.sql, domain.impl.namespace, cache_flag)))


if __name__ == "__main__":
    main()