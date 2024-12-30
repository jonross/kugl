"""
Process Kugel queries.
If you're looking for Kugel's "brain", you've found it.
See also tables.py
"""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
from typing import Tuple, Set, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field
from tabulate import tabulate

from .config import Config, UserConfig
from .registry import Schema
from .tables import TableFromCode, TableFromConfig
from kugel.util import fail, SqliteDb, to_size, to_utc, kugel_home, clock, ConfigPath, debugging, to_age

# Needed to locate the built-in table builders by class name.
import kugel.builtins.kubernetes

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

    def __init__(self, schema: Schema, config: Config, context_name: str):
        """
        :param config: the parsed user configuration file
        :param context_name: the Kubernetes context to use, e.g. "minikube", "research-cluster"
        """
        self.schema = schema
        self.config = config
        self.context_name = context_name
        self.cache = DataCache(self.config, kugel_home() / "cache" / self.context_name)
        # Maps resource name e.g. "pods" to the response from "kubectl get pods -o json"
        self.data = {}
        self.db = SqliteDb()
        add_custom_functions(self.db.conn)

    def query_and_format(self, query: Query) -> str:
        """Execute a Kugel query and format the rsults for stdout."""
        rows, headers = self.query(query)
        return tabulate(rows, tablefmt="plain", floatfmt=".1f", headers=headers)

    def query(self, query: Query) -> Tuple[list[Tuple], list[str]]:
        """Execute a Kugel query but don't format the results.
        :return: a tuple of (rows, column names)
        """

        # Load built-ins for the target schema
        builtins_yaml = ConfigPath(__file__).parent.parent / "builtins" / f"{self.schema.name}.yaml"
        if builtins_yaml.exists():
            builtins = UserConfig(**builtins_yaml.parse_yaml())
            self.config.resources.update({r.name: r for r in builtins.resources})
            self.config.create.update({c.table: c for c in builtins.create})

        # Verify user-defined tables have the needed resources
        for table in self.config.create.values():
            if table.resource not in self.config.resources:
                fail(f"Table '{table.table}' needs unknown resource '{table.resource}'")

        # Reconcile tables created / extended in the config file with tables defined in code, and
        # generate the table builders.
        tables = {}
        for name in {t.name for t in query.table_refs}:
            code_creator = self.schema.tables.get(name)
            config_creator = self.config.create.get(name)
            extender = self.config.extend.get(name)
            if code_creator and config_creator:
                fail(f"Pre-defined table {name} can't be created from init.yaml")
            if code_creator:
                tables[name] = TableFromCode(code_creator, extender)
            elif config_creator:
                tables[name] = TableFromConfig(name, config_creator, extender)
            else:
                # Some of the named tables may be CTEs, so it's not an error if we can't create
                # them.  If actually missing when we reach the query, let SQLite issue the error.
                pass

        resources_used = {t.resource for t in tables.values()}
        if "pods" in resources_used:
            # This is fake, _get_objects knows to get it via "kubectl get pods" not as JSON.
            # TODO: move this hack to kubernetes.py
            resources_used.add("pod_statuses")

        # Identify what to fetch vs what's stale or expired.
        refreshable, max_staleness = self.cache.advise_refresh(query.namespace, resources_used, query.cache_flag)
        if not self.config.settings.reckless and max_staleness is not None:
            print(f"(Data may be up to {max_staleness} seconds old.)", file=sys.stderr)
            clock.CLOCK.sleep(0.5)

        # Retrieve resource data in parallel.  If fetching from Kubernetes, update the cache;
        # otherwise just read from the cache.
        def fetch(kind):
            try:
                if kind in refreshable:
                    self.data[kind] = self.schema.impl.get_objects(kind, self.config)
                    self.cache.dump(query.namespace, kind, self.data[kind])
                else:
                    self.data[kind] = self.cache.load(query.namespace, kind)
            except Exception as e:
                fail(f"Failed to get {kind} objects: {e}")
        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in pool.map(fetch, resources_used):
                pass

        # There won't really be a pod_statuses table, just grab the statuses and put them
        # on the pod objects.  Drop the pods where we didn't get status back from kubectl.
        # TODO: move this hack to kubernetes.py
        if "pods" in resources_used:
            statuses = self.data.get("pod_statuses")
            def pod_with_updated_status(pod):
                metadata = pod["metadata"]
                status = statuses.get(f"{metadata['namespace']}/{metadata['name']}")
                if status:
                    pod["kubectl_status"] = status
                    return pod
                return None
            self.data["pods"]["items"] = list(filter(None, map(pod_with_updated_status, self.data["pods"]["items"])))
            del self.data["pod_statuses"]

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

    def __init__(self, config: Config, dir: Path):
        """
        :param config: the parsed user configuration file
        :param dir: root of the cache folder tree; paths are of the form
            <kubernetes context>/<namespace>.<resource kind>.json
        """
        self.config = config
        self.dir = dir
        dir.mkdir(parents=True, exist_ok=True)

    def advise_refresh(self, namespace: str, kinds: Set[str], flag: CacheFlag) -> Tuple[Set[str], int]:
        """Determine which resources to use from cache or to refresh.

        :param namespace: the Kubernetes namespace to query, or ALL_NAMESPACE
        :param kinds: the resource types to consider
        :param flag: the user-specified cache behavior
        :return: a tuple of (refreshable, max_age) where refreshable is the set of resources types
            to update, and max_age is the maximum age of the resources that won't be updated.
        """
        if flag == ALWAYS_UPDATE:
            # Refresh everything and don't issue a "stale data" warning
            return kinds, None
        # Find what's expired or missing
        cache_ages = {kind: self.age(self.cache_path(namespace, kind)) for kind in kinds}
        expired = {kind for kind, age in cache_ages.items() if age is not None and age >= self.config.settings.cache_timeout.value}
        missing = {kind for kind, age in cache_ages.items() if age is None}
        # Always refresh what's missing, and possibly also what's expired
        # Stale data warning for everything else
        refreshable = missing if flag == NEVER_UPDATE else expired | missing
        if debugging("cache"):
            print("Requested", kinds)
            print("Ages", cache_ages)
            print("Expired", expired)
            print("Missing", missing)
            print("Refreshable", refreshable)
        max_age = max((cache_ages[kind] for kind in (kinds - refreshable)), default=None)
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
            return None
        return int(clock.CLOCK.now() - path.stat().st_mtime)


def add_custom_functions(db):
    db.create_function("to_size", 1, lambda x: to_size(x, iec=True))
    # This must be a lambda because the clock is patched in unit tests
    db.create_function("now", 0, lambda: clock.CLOCK.now())
    db.create_function("to_age", 1, to_age)
    db.create_function("to_utc", 1, to_utc)


