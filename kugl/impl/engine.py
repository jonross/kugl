"""
Process Kugl queries.
If you're looking for Kugl's "brain", you've found it.
See also tables.py
"""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
from typing import Tuple, Set, Optional, Literal

import funcy as fn
from pydantic import BaseModel, ConfigDict, Field
from tabulate import tabulate

from .config import ResourceDef, Settings
from .registry import Schema, Resource
from kugl.util import fail, SqliteDb, to_size, to_utc, kugl_home, clock, debugging, to_age, run, Age, KPath, \
    kube_context

# Cache behaviors
# TODO consider an enum

ALWAYS_UPDATE, CHECK, NEVER_UPDATE = 1, 2, 3
CacheFlag = Literal[ALWAYS_UPDATE, CHECK, NEVER_UPDATE]


class Query(BaseModel):
    """A SQL query + query-related behaviors"""
    sql: str

    @property
    def table_refs(self) -> Set["TableRef"]:
        # Determine which tables are needed for the query by looking for symmbols that follow
        # FROM and JOIN.  Some of these may be CTEs, so don't assume they're all availabie in
        # Kubernetes, just pick out the ones we know about and let SQLite take care of
        # "unknown table" errors.
        # FIXME: use sqlparse package
        sql = self.sql.replace("\n", " ")
        refs = set(re.findall(r"(?<=from|join)\s+([.\w]+)", sql, re.IGNORECASE))
        return {TableRef.parse(ref) for ref in refs}

    @property
    def sql_schemaless(self) -> str:
        """Return the SQL query with schema hints removed."""
        sql = self.sql.replace("\n", " ")
        return re.sub(r"((from|join)\s+)[^.\s]+\.", r"\1", sql, flags=re.IGNORECASE)


class TableRef(BaseModel):
    """A reference to a table in a query."""
    model_config = ConfigDict(frozen=True)
    schema_name: str = Field(..., alias="schema")  # e.g. "kubernetes"
    name: str  # e.g. "pods"

    @classmethod
    def parse(cls, ref: str):
        """Parse a table reference of the form "pods" or "kubernetes.pods".
        SQLite doesn't actually support schemas, so the schema is just a hint.
        We replace the dot with an underscore to make it a valid table name."""
        parts = ref.split(".")
        if len(parts) == 1:
            return cls(schema="kubernetes", name=parts[0])
        if len(parts) == 2:
            if parts[0] == "k8s":
                parts[0] = "kubernetes"
            return cls(schema=parts[0], name=parts[1])
        fail(f"Invalid table reference: {ref}")


class Engine:

    def __init__(self, schema: Schema, args, cache_flag: CacheFlag, settings: Settings):
        """
        :param config: the parsed user settings file
        """
        self.schema = schema
        self.args = args
        self.cache_flag = cache_flag
        self.settings = settings
        self.cache = DataCache(kugl_home() / "cache", self.settings.cache_timeout)
        # Maps resource name e.g. "pods" to the response from "kubectl get pods -o json"
        self.data = {}
        self.db = SqliteDb()
        add_custom_functions(self.db.conn)

    def query_and_format(self, query: Query) -> str:
        """Execute a Kugl query and format the rsults for stdout."""
        rows, headers = self.query(query)
        return tabulate(rows, tablefmt="plain", floatfmt=".1f", headers=headers)

    def query(self, query: Query) -> Tuple[list[Tuple], list[str]]:
        """Execute a Kugl query but don't format the results.
        :return: a tuple of (rows, column names)
        """

        # Reconcile tables created / extended in the config file with tables defined in code, and
        # generate the table builders.
        tables = {}
        for name in {t.name for t in query.table_refs}:
            # Some of the named tables may be CTEs, so it's not an error if we can't create
            # them.  If actually missing when we reach the query, let SQLite issue the error.
            if (table := self.schema.table_builder(name)) is not None:
                tables[name] = table

        # Identify what to fetch vs what's stale or expired.
        resources_used = self.schema.resources_used(tables.values())
        for r in resources_used:
            r.handle_cli_options(self.args)
        refreshable, max_staleness = self.cache.advise_refresh(resources_used, self.cache_flag)
        if not self.settings.reckless and max_staleness is not None:
            print(f"(Data may be up to {max_staleness} seconds old.)", file=sys.stderr)
            clock.CLOCK.sleep(0.5)

        # Retrieve resource data in parallel.  If fetching from Kubernetes, update the cache;
        # otherwise just read from the cache.
        def fetch(resource: Resource):
            try:
                if resource in refreshable:
                    self.data[resource.name] = resource.get_objects()
                    if resource.cacheable:
                        self.cache.dump(resource, self.data[resource.name])
                else:
                    self.data[resource.name] = self.cache.load(resource)
            except Exception as e:
                fail(f"Failed to get {resource.name} objects: {e}")
        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in pool.map(fetch, resources_used):
                pass

        # Create tables in SQLite
        for table in tables.values():
            table.build(self.db, self.data[table.resource])

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

    def advise_refresh(self, resources: Set[ResourceDef], flag: CacheFlag) -> Tuple[Set[str], int]:
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
        cacheable = {r for r in resources if r.cacheable}
        non_cacheable = {r for r in resources if not r.cacheable}
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

    def dump(self, resource: Resource, data: dict):
        self.cache_path(resource).write_text(json.dumps(data))

    def load(self, resource: Resource) -> dict:
        return json.loads(self.cache_path(resource).read_text())

    def cache_path(self, resource) -> Path:
        path = self.dir / resource.cache_path()
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
    db.create_function("to_size", 1, lambda x: to_size(x, iec=True))
    # This must be a lambda because the clock is patched in unit tests
    db.create_function("now", 0, lambda: clock.CLOCK.now())
    db.create_function("to_age", 1, to_age)
    db.create_function("to_utc", 1, to_utc)


