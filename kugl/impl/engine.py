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

import yaml
from pydantic import BaseModel, ConfigDict, Field
from tabulate import tabulate

from .config import ResourceDef, Settings
from .registry import Schema
from kugl.util import fail, SqliteDb, to_size, to_utc, kugl_home, clock, debugging, to_age, run, Age, KPath

# Needed to locate the built-in table builders by class name.
import kugl.builtins.kubernetes

# Cache behaviors
# TODO consider an enum

ALWAYS_UPDATE, CHECK, NEVER_UPDATE = 1, 2, 3
CacheFlag = Literal[ALWAYS_UPDATE, CHECK, NEVER_UPDATE]


class Query(BaseModel):
    """A SQL query + query-related behaviors"""
    sql: str
    # TODO: move this elsewhere, it's K8S-specific
    namespace: str = "default"
    cache_flag: CacheFlag = ALWAYS_UPDATE

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

    def __init__(self, schema: Schema, settings: Settings, context_name: str):
        """
        :param config: the parsed user settings file
        :param context_name: the Kubernetes context to use, e.g. "minikube", "research-cluster"
        """
        self.schema = schema
        self.settings = settings
        self.context_name = context_name
        self.cache = DataCache(kugl_home() / "cache" / self.context_name, self.settings.cache_timeout)
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
        refreshable, max_staleness = self.cache.advise_refresh(query.namespace, resources_used, query.cache_flag)
        if not self.settings.reckless and max_staleness is not None:
            print(f"(Data may be up to {max_staleness} seconds old.)", file=sys.stderr)
            clock.CLOCK.sleep(0.5)

        # Retrieve resource data in parallel.  If fetching from Kubernetes, update the cache;
        # otherwise just read from the cache.
        def fetch(res: ResourceDef):
            try:
                if res in refreshable:
                    self.data[res.name] = self._get_objects(res)
                    self.cache.dump(query.namespace, res.name, self.data[res.name])
                else:
                    self.data[res.name] = self.cache.load(query.namespace, res.name)
            except Exception as e:
                fail(f"Failed to get {res.name} objects: {e}")
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

    def _get_objects(self, resource: ResourceDef) -> dict:
        """Called for a cache miss, go actually fetch resources.
        Handle built-in resources here, and dispatch to schema implementation for those
        that aren't.
        """
        def parse(text):
            if not text:
                return {}
            if text[0] in "{[":
                return json.loads(text)
            return yaml.safe_load(text)

        if resource.file is not None:
            if resource.file == "stdin":
                return parse(sys.stdin.read())
            try:
                return parse(Path(resource.file).read_text())
            except OSError as e:
                fail(f"Failed to read {resource.file}", e)

        if resource.exec is not None:
            _, out, _ = run(resource.exec)
            return parse(out)

        return self.schema.impl.get_objects(resource.name, resource.namespaced)


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

    def advise_refresh(self, namespace: str, resources: Set[ResourceDef], flag: CacheFlag) -> Tuple[Set[str], int]:
        """Determine which resources to use from cache or to refresh.

        :param namespace: the Kubernetes namespace to query, or ALL_NAMESPACE
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
        cache_ages = {r: self.age(self.cache_path(namespace, r.name)) for r in cacheable}
        expired = {r for r, age in cache_ages.items() if age is not None and age >= self.timeout.value}
        missing = {r for r, age in cache_ages.items() if age is None}
        # Always refresh what's missing or non-cacheable, and possibly also what's expired
        # Stale data warning for everything else
        refreshable = missing if flag == NEVER_UPDATE else expired | missing
        max_age = max((cache_ages[r] for r in (cacheable - refreshable)), default=None)
        refreshable.update(non_cacheable)
        if debugging("cache"):
            print("Requested", [r.name for r in resources])
            print("Cacheable", [r.name for r in cacheable])
            print("Non-cacheable", [r.name for r in non_cacheable])
            print("Ages", " ".join(f"{r.name}={age}" for r, age in cache_ages.items()))
            print("Expired", [r.name for r in expired])
            print("Missing", [r.name for r in missing])
            print("Refreshable", [r.name for r in refreshable])
        return refreshable, max_age

    def cache_path(self, namespace: str, kind: str) -> Path:
        return self.dir / f"{namespace}.{kind}.json"

    def dump(self, namespace: str, kind: str, data: dict):
        self.cache_path(namespace, kind).write_text(json.dumps(data))

    def load(self, namespace: str, kind: str) -> dict:
        return json.loads(self.cache_path(namespace, kind).read_text())

    def age(self, path: Path) -> Optional[int]:
        """The age of a file in seconds, relative to the current time, or None if it doesn't exist."""
        if not path.exists():
            if debugging("cache"):
                print("Missing cache file", path)
            return None
        age_secs = int(clock.CLOCK.now() - path.stat().st_mtime)
        if debugging("cache"):
            print(f"Found cache file (age = {to_age(age_secs)})", path)
        return age_secs


def add_custom_functions(db):
    db.create_function("to_size", 1, lambda x: to_size(x, iec=True))
    # This must be a lambda because the clock is patched in unit tests
    db.create_function("now", 0, lambda: clock.CLOCK.now())
    db.create_function("to_age", 1, to_age)
    db.create_function("to_utc", 1, to_utc)


