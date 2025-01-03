"""
Command-line entry point.
"""

import os
from argparse import ArgumentParser
import sys
from sqlite3 import DatabaseError
from typing import List, Optional, Union

import yaml

from kugl.impl.registry import Registry
from kugl.impl.engine import Engine, Query, CHECK, NEVER_UPDATE, ALWAYS_UPDATE
from kugl.impl.config import UserConfig, UserInit, parse_file
from kugl.util import Age, fail, debug, debugging, kugl_home, kube_home, ConfigPath, dprint, KuglError


def main() -> None:
    main1(sys.argv[1:])


def main1(argv: List[str]):

    if "KUGL_UNIT_TESTING" in os.environ and "KUGL_MOCKDIR" not in os.environ:
        # Never enter main in tests unless test_home fixture is in use, else we could read
        # the user's init file.
        sys.exit("Unit test state error")

    try:
        return main2(argv)
    except KuglError as e:
        # These are raised by fail(), we only want the error message.
        severe, exc = False, e
    except DatabaseError as e:
        # DB errors are common when writing queries, don't make them look like a crash.
        severe, exc = False, e
    except Exception as e:
        severe, exc = True, e
    if severe or debugging() or "KUGL_UNIT_TESTING" in os.environ:
        raise exc
    print(exc, file=sys.stderr)
    sys.exit(1)


def main2(argv: List[str]):

    kugl_home().mkdir(exist_ok=True)
    if not argv:
        fail("missing sql query")

    # Load init file.
    init_file = ConfigPath(kugl_home() / "init.yaml")
    init, errors = parse_file(UserInit, init_file)
    if errors:
        fail("\n".join(errors))

    # Check for shortcuts now, because they can include command line options.  But the
    # command line as given also applies.  So we have to treat the last arg as SQL or
    # shortcut name, even before we see the options.
    if " " not in argv[-1]:
        if not (new_argv := init.shortcuts.get(argv[-1])):
            fail(f"No shortcut named '{argv[-1]}' is defined in ~/.kugl/init.yaml")
        return main1(argv[:-1] + new_argv)

    # Need the query schema for command line parsing.
    # FIXME: Move the namespace & cache flag out of the query
    rgy = Registry.get()
    query = Query(sql=argv[-1])
    schema_refs = {ref.schema_name for ref in query.table_refs}
    if len(schema_refs) == 0:
        schema = rgy.get_schema("empty")
    elif len(schema_refs) == 1:
        schema = rgy.get_schema(next(iter(schema_refs)))
    else:
        fail("Cross-schema query not implemented yet")

    ap = ArgumentParser()
    schema.impl.add_cli_options(ap)
    ap.add_argument("-D", "--debug", type=str)
    ap.add_argument("-c", "--cache", default=False, action="store_true")
    ap.add_argument("-r", "--reckless", default=False, action="store_true")
    ap.add_argument("-t", "--timeout", type=str)
    ap.add_argument("-u", "--update", default=False, action="store_true")
    ap.add_argument("sql")
    args = ap.parse_args(argv)

    schema.impl.handle_cli_options(args)
    if args.cache and args.update:
        fail("Cannot use both -c/--cache and -u/--update")

    cache_flag = ALWAYS_UPDATE if args.update else NEVER_UPDATE if args.cache else CHECK
    if args.debug:
        debug(args.debug.split(","))
    if args.reckless:
        init.settings.reckless = True
    if args.timeout:
        init.settings.cache_timeout = Age(args.timeout)
    dprint("init", f"Settings: {init.settings}")

    kube_config = kube_home() / "config"
    if not kube_config.exists():
        fail(f"Missing {kube_config}, can't determine current context")

    current_context = (yaml.safe_load(kube_config.read_text()) or {}).get("current-context")
    if not current_context:
        fail("No current context, please run kubectl config use-context ...")

    engine = Engine(schema, init.settings, current_context)
    # FIXME bad reference to namespace
    sql = query.sql_schemaless
    print(engine.query_and_format(Query(sql=sql, namespace=schema.impl.ns, cache_flag=cache_flag)))


if __name__ == "__main__":
    main()