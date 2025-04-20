import os
from concurrent.futures import ThreadPoolExecutor
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Tuple, Set, Optional, Literal

from tabulate import tabulate

from .config import Settings, DEFAULT_SCHEMA
from .registry import Schema, Resource, Registry
from ..util import fail, SqliteDb, to_size, to_utc, kugl_cache, clock, debugging, to_age, Age, KPath, Query
from .tables import Table

# Cache behaviors
ALWAYS_UPDATE, CHECK, NEVER_UPDATE = 1, 2, 3
CacheFlag = Literal[ALWAYS_UPDATE, CHECK, NEVER_UPDATE]


@dataclass
class ResourceRef:
    """Associate a Resource with a Schema in a hashable type (for set memberhip).
    This avoids having Resource itself be hashable, which is an unnecessary constraint."""
    schema: Schema
    resource: Resource

    @property
    def name(self):
        return f"{self.schema.name}.{self.resource.name}"

    def __eq__(self, other):
        return self.schema.name == other.schema.name and self.resource.name == other.resource.name

    def __hash__(self):
        return hash((self.schema.name, self.resource.name))

    def __lt__(self, other):
        return (self.schema.name, self.resource.name) < (other.schema.name, other.resource.name)


class Engine:
    """Entry point for executing Kugl queries."""

    def __init__(self, args, cache_flag: CacheFlag, settings: Settings):
        """
        :param args: the parsed command line arguments, from argparse
        :param cache_flag: the cache behavior, from -c or -u option
        :param config: the parsed user settings file
        """
        self.args = args
        self.cache_flag = cache_flag
        self.settings = settings
        self.cache = DataCache(kugl_cache(), self.settings.cache_timeout)
        # Maps resource name e.g. "pods" to the response from "kubectl get pods -o json"
        self.data = {}
        self.db = SqliteDb()
        add_custom_functions(self.db.conn)

    def query_and_format(self, query: Query) -> str:
        """Execute a Kugl query and format the results for stdout."""
        rows, headers = self.query(query)
        return tabulate(rows, tablefmt="plain", floatfmt=".1f",
                        headers=(() if self.settings.no_headers else headers))

    def query(self, query: Query) -> Tuple[list[Tuple], list[str]]:
        """Execute a Kugl query but don't format the results.
        :return: a tuple of (rows, column names)
        """

        # Identify schemas named in the query and read their configs.
        # If none named, assume the "kubernetes" schema.
        schemas_named = query.schemas_named()
        if schemas_named:
            multi_schema = True
            # Make a separate in-memory db per schema
            for name in schemas_named:
                self.db.execute(f"ATTACH DATABASE ':memory:' AS '{name}'")
        else:
            schemas_named = {"kubernetes"}
            multi_schema = False
        registry = Registry.get()
        schemas = {name: registry.get_schema(name).read_configs(self.settings.init_path) for name in schemas_named}

        # Reconcile tables created / extended in the config file with tables defined in code,
        # generate the table builders, and identify the required resources. Note: some of the
        # named tables may be CTEs, so it's not a problem if we can't create them.  SQLite
        # will say "no such table" when we issue the query.
        tables: list[tuple[Table, ResourceRef]] = []
        resource_refs: set[ResourceRef] = set()
        for named_table in query.named_tables:
            schema = schemas[named_table.schema_name or DEFAULT_SCHEMA]
            if table := schema.table_builder(named_table.name):
                resource_ref = ResourceRef(schema, schema.resource_for(table))
                tables.append((table, resource_ref))
                resource_refs.add(resource_ref)

        # Identify what to fetch vs what's stale or expired.
        for r in resource_refs:
            r.resource.handle_cli_options(self.args)
        refreshable, max_staleness = self.cache.advise_refresh(resource_refs, self.cache_flag)
        if not self.settings.reckless and max_staleness is not None:
            print(f"(Data may be up to {max_staleness} seconds old.)", file=sys.stderr)
            clock.CLOCK.sleep(0.5)

        # Retrieve resource data in parallel.  If actually fetching externally, update the cache;
        # otherwise just read from the cache.
        def fetch(ref: ResourceRef):
            try:
                if ref in refreshable:
                    self.data[ref.name] = ref.resource.get_objects()
                    if ref.resource.cacheable:
                        self.cache.dump(ref, self.data[ref.name])
                else:
                    self.data[ref.name] = self.cache.load(ref)
            except Exception as e:
                fail(f"failed to fetch resource {ref.name}: {e}")
        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in pool.map(fetch, resource_refs):
                pass

        # Create tables in SQLite
        for table, resource_ref in tables:
            table.build(self.db, self.data[resource_ref.name], multi_schema)

        column_names = []
        rows = self.db.query(query.sql, names=column_names)
        # %g is susceptible to outputting scientific notation, which we don't want.
        # but %f always outputs trailing zeros, which we also don't want.
        # So turn every value x in each row into an int if x == float(int(x))
        truncate = lambda x: int(x) if isinstance(x, float) and x == float(int(x)) else x
        rows = [[truncate(x) for x in row] for row in rows]
        return rows, column_names


class DataCache:
    """Manage the cached JSON data from Kubectl.
    This is a separate class for ease of unit testing.
    """

    def __init__(self, dir: KPath, timeout: Age):
        """
        :param dir: root of the cache folder tree; paths are of the form
            <kubernetes context>/<namespace>.<resource kind>.json
        :param timeout: age at which cached data is considered stale
        """
        self.dir = dir
        dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    def advise_refresh(self, resources: Set[ResourceRef], flag: CacheFlag) -> Tuple[Set[str], int]:
        """Determine which resources to use from cache or to refresh.

        :param resources: the resource types to consider
        :param flag: the user-specified cache behavior
        :return: a tuple of (refreshable, max_age) where refreshable is the set of resources types
            to update, and max_age is the maximum age of the resources that won't be updated.
        """
        if flag == ALWAYS_UPDATE:
            # Refresh everything and don't issue a "stale data" warning
            return resources, None
        # Find what's expired or missing
        cacheable = {r for r in resources if r.resource.cacheable}
        non_cacheable = {r for r in resources if not r.resource.cacheable}
        # Sort here for deterministic behavior in unit tests
        cache_ages = {r: self.age(self.cache_path(r)) for r in sorted(cacheable)}
        expired = {r for r, age in cache_ages.items() if age is not None and age >= self.timeout.value}
        missing = {r for r, age in cache_ages.items() if age is None}
        # Always refresh what's missing or non-cacheable, and possibly also what's expired
        # Stale data warning for everything else
        refreshable = set(missing) if flag == NEVER_UPDATE else expired | missing
        max_age = max((cache_ages[r] for r in (cacheable - refreshable)), default=None)
        refreshable.update(non_cacheable)
        if debug := debugging("cache"):
            # Sort here for deterministic output in unit tests
            names = lambda res_list: "[" + " ".join(sorted(r.name for r in res_list)) + "]"
            debug("requested", names(resources))
            debug("cacheable", names(cacheable))
            debug("non-cacheable", names(non_cacheable))
            debug("ages", " ".join(f"{r.name}={age}" for r, age in sorted(cache_ages.items())))
            debug("expired", names(expired))
            debug("missing", names(missing))
            debug("refreshable", names(refreshable))
        return refreshable, max_age

    def dump(self, ref: ResourceRef, data: dict):
        self.cache_path(ref).write_text(json.dumps(data))

    def load(self, ref: ResourceRef) -> dict:
        return json.loads(self.cache_path(ref).read_text())

    def cache_path(self, ref: ResourceRef) -> Path:
        path = self.dir / ref.schema.name / ref.resource.cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def age(self, path: Path) -> Optional[int]:
        """The age of a file in seconds, relative to the current time, or None if it doesn't exist."""
        debug = debugging("cache")
        if not path.exists():
            if debug:
                debug("missing cache file", path)
            return None
        age_secs = int(clock.CLOCK.now() - path.stat().st_mtime)
        if debug:
            debug(f"found cache file (age = {to_age(age_secs)})", path)
        return age_secs


def add_custom_functions(db):

    def wrap(name, func):
        def wrapped(*args):
            if args and not args[0]:
                return None
            try:
                return func(*args)
            except Exception as e:
                # Can't use fail() here because SQLite won't offer detail
                print(f"kugl: exception in extension function {name}: {e}", file=sys.stderr)
                os._exit(1)
        return wrapped

    db.create_function("to_size", 1, wrap("to_size", lambda x: to_size(x, iec=True)))
    # This must be a lambda because the clock is patched in unit tests
    db.create_function("now", 0, wrap("now", lambda: clock.CLOCK.now()))
    db.create_function("to_age", 1, wrap("to_age", to_age))
    db.create_function("to_utc", 1, wrap("to_age", to_utc))