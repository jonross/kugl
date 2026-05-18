"""
Command-line entry point.
"""

import argparse
import os
import re
from argparse import ArgumentParser
import sys
from sqlite3 import DatabaseError
from typing import List, Optional, Type

from kugl.impl.registry import Registry
from kugl.impl.engine import Engine, CHECK, NEVER_UPDATE, ALWAYS_UPDATE, CacheFlag
from kugl.impl.config import UserInit, parse_file, Settings, Shortcut, SecondaryUserInit
from kugl.util import (
    Age,
    fail,
    debug_features,
    kugl_home,
    ConfigPath,
    debugging,
    KuglError,
    Query,
    failure_preamble,
)

# Register built-ins immediately because they're needed for command-line parsing
import kugl.builtins.resources  # noqa: F401
import kugl.builtins.schemas.kubernetes  # noqa: F401


def main() -> None:
    # This one line is separate from the rest of main() logic so we don't meddle with
    # sys.argv in unit tests.
    sys.argv[0] = "kugl"
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


def main2(argv: List[str], init: Optional[UserInit] = None):
    kugl_home().mkdir(exist_ok=True)
    if not argv:
        fail("Missing sql query")

    if argv[0] == "init":
        _handle_init_command()
        return

    if argv[0] == "schema" or argv[0] == "--schema":
        if len(argv) < 2:
            fail("Missing schema or table name")
        if init is None:
            init, shortcuts = _merge_init_files()
        print(Registry.get().printable_schema(argv[1], init.settings.init_path))
        return

    if init is None:
        init, shortcuts = _merge_init_files()

    ap = ArgumentParser()
    Registry.get().augment_cli(ap)
    args, cache_flag, extras = parse_args(argv, ap, init.settings)

    # Reject unrecognized options for direct SQL queries (shortcuts handle this separately).
    if " " in args.sql and extras:
        ap.error(f"unrecognized arguments: {' '.join(extras)}")

    # Check for shortcut and reparse, because they can contain command-line options.
    if " " not in args.sql:
        if not (shortcut := shortcuts.get(args.sql)):
            fail(f"No shortcut named '{args.sql}' is defined")
        bad = [e for e in extras if e.startswith('-')]
        if bad:
            fail(f"Unrecognized options: {' '.join(bad)}")
        if len(extras) != len(shortcut.params):
            if shortcut.params:
                fail(f"Shortcut '{shortcut.name}' requires {len(shortcut.params)} argument(s): {', '.join(shortcut.params)}")
            else:
                fail(f"Shortcut '{shortcut.name}' takes no arguments")
        bindings = dict(zip(shortcut.params, extras))
        expanded = [re.sub(r'\{\{(\w+)\}\}', lambda m: bindings[m.group(1)], a) for a in shortcut.args]
        idx = len(argv) - len(extras) - 1
        return main2(argv[:idx] + expanded, init)

    if args.debug:
        debug_features(args.debug.split(","))
    if debug := debugging("init"):
        debug(f"settings: {init.settings}")

    engine = Engine(args, cache_flag, init.settings)
    print(engine.query_and_format(Query(args.sql), args.output))


def parse_args(
    argv: list[str], ap: ArgumentParser, settings: Settings
) -> tuple[argparse.Namespace, CacheFlag, list[str]]:
    """Add stock arguments to parser, parse the command line, and override settings."""
    ap.add_argument("-c", "--context", type=str, help="kubectl context to use")
    ap.add_argument("-D", "--debug", type=str, help="comma-separated debug topics: cache, extract, itemize; see docs for more")
    ap.add_argument("-H", "--no-headers", default=False, action="store_true", help="suppress column headers")
    ap.add_argument("-o", "--output", choices=["table", "csv", "json"], default="table", help="output format (default: table)")
    ap.add_argument("-q", "--quiet", default=False, action="store_true", help="suppress stale-data warnings")
    ap.add_argument("-r", "--refresh", default=False, action="store_true", help="force refresh of all cached data")
    ap.add_argument("-s", "--stale", default=False, action="store_true", help="use cached data even if stale")
    ap.add_argument("-t", "--timeout", type=str, help="cache timeout, e.g. 5m or 30s (default: 2m)")
    ap.add_argument("sql", help="SQL query or shortcut name")
    args, extras = ap.parse_known_args(argv)
    if args.stale and args.refresh:
        fail("Cannot use both -s/--stale and -r/--refresh")
    if args.timeout:
        settings.cache_timeout = Age(args.timeout)
    if args.quiet:
        settings.quiet = True
    if args.no_headers:
        settings.no_headers = True
    return args, (ALWAYS_UPDATE if args.refresh else NEVER_UPDATE if args.stale else CHECK), extras


def _merge_init_files() -> tuple[UserInit, dict[str, Shortcut]]:
    """Read the primary init.yaml, then add shortcuts from other init.yaml on the init_path"""

    shortcuts = {}

    def _parse_init(path: ConfigPath, model_class: Type):
        with failure_preamble(f"Errors in {path}:"):
            return parse_file(model_class, path)

    def _merge_init(init: SecondaryUserInit):
        with failure_preamble(f"Errors in {init._source}:"):
            for shortcut in init.shortcuts:
                if shortcut.name in shortcuts:
                    fail(f"Duplicate shortcut '{shortcut.name}'")
                shortcuts[shortcut.name] = shortcut

    init = _parse_init(ConfigPath(kugl_home() / "init.yaml"), UserInit)
    for folder in init.settings.init_path:
        # Note: config.py prevents ~/.kugl from appearing in init_path
        secondary = _parse_init(ConfigPath(folder) / "init.yaml", SecondaryUserInit)
        _merge_init(secondary)
    _merge_init(init)
    return init, shortcuts


def _handle_init_command():
    """Initialize kugl configuration by creating ~/.kugl and recommended kubernetes.yaml."""
    config_dir = kugl_home()
    config_dir.mkdir(exist_ok=True)

    kubernetes_yaml = config_dir / "kubernetes.yaml"
    if kubernetes_yaml.exists():
        fail(f"{kubernetes_yaml} already exists. Remove it first if you want to reinitialize.")

    recommended_config = """extend:
  - table: nodes
    columns:
      - name: instance_type
        label:
          - node.kubernetes.io/instance-type
          - beta.kubernetes.io/instance-type
"""

    kubernetes_yaml.write_text(recommended_config)
    print(f"Created {kubernetes_yaml}")


if __name__ == "__main__":
    main()
