"""
Process Kugel queries.
If you're looking for Kugel's "brain", you've found it.
"""

from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
from typing import Tuple, Set, Optional, Dict

import jmespath
from tabulate import tabulate
import yaml

from kugel.model.config import Config, UserConfig, ColumnDef, ExtendTable, CreateTable
from kugel.model.constants import CacheFlag, ALL_NAMESPACE, WHITESPACE, ALWAYS_UPDATE, NEVER_UPDATE
from .registry import get_domain, TableDef
from .jross import run, SqliteDb
from .utils import add_custom_functions, kugel_home, fail, set_parent
import kugel.impl.time as ktime

# Needed to locate the built-in table builders by class name.
import kugel.impl.tables

Query = namedtuple("Query", ["sql", "namespace", "cache_flag"])


class Engine:

    def __init__(self, config: Config, context_name: str):
        """
        :param config: the parsed user configuration file
        :param context_name: the Kubernetes context to use, e.g. "minikube", "research-cluster"
        """
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

        builtins = UserConfig(**yaml.safe_load((Path(__file__).parent / "builtins.yaml").read_text()))
        self.config.resources.update({r.name: r for r in builtins.resources})
        self.config.create.update({c.table: c for c in builtins.create})

        # Determine which tables are needed for the query by looking for symmbols that follow
        # FROM and JOIN.  Some of these may be CTEs, so don't assume they're all availabie in
        # Kubernetes, just pick out the ones we know about and let SQLite take care of
        # "unknown table" errors.
        kql = query.sql.replace("\n", " ")
        tables_named = set(re.findall(r"(?<=from|join)\s+(\w+)", kql, re.IGNORECASE))

        # Reconcile tables created / extended in the config file with tables defined in code, and
        # generate the table builders.
        domain = get_domain("kubernetes")
        tables = {}
        for name in tables_named:
            code_creator = domain.tables.get(name)
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
            # This is fake, _get_objects knows to get it via "kubectl get pods" not as JSON
            resources_used.add("pod_statuses")

        # Identify what to fetch vs what's stale or expired.
        refreshable, max_staleness = self.cache.advise_refresh(query.namespace, resources_used, query.cache_flag)
        if not self.config.settings.reckless and max_staleness is not None:
            print(f"(Data may be up to {max_staleness} seconds old.)", file=sys.stderr)
            ktime.CLOCK.sleep(0.5)

        # Retrieve resource data in parallel.  If fetching from Kubernetes, update the cache;
        # otherwise just read from the cache.
        def fetch(kind):
            try:
                if kind in refreshable:
                    self.data[kind] = domain.impl.get_objects(kind, self.config)
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
        if "pods" in resources_used:
            def pod_with_updated_status(pod):
                status = self.data["pod_statuses"].get(pod["metadata"]["name"])
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
        rows = self.db.query(kql, names=column_names)
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
        return int(ktime.CLOCK.now() - path.stat().st_mtime)


# TODO: make abstract
# TODO: completely sever from user configs
class Table:
    """The engine-level representation of a table, independent of the config file format"""

    def __init__(self, name: str, resource: str, schema: str, extras: list[ColumnDef]):
        """
        :param name: the table name, e.g. "pods"
        :param resource: the Kubernetes resource type, e.g. "pods"
        :param schema: the SQL schema, e.g. "name TEXT, age INTEGER"
        :param extras: extra column definitions from user configs (not from Python-defined tables)
        """
        self.name = name
        self.resource = resource
        self.schema = schema
        self.extras = extras

    def build(self, db, kube_data: dict):
        """Create the table in SQLite and insert the data.

        :param db: the SqliteDb instance
        :param kube_data: the JSON data from 'kubectl get'
        """
        db.execute(f"CREATE TABLE {self.name} ({self.schema})")
        item_rows = list(self.make_rows(kube_data))
        if item_rows:
            if self.extras:
                extend_row = lambda item, row: row + tuple(column.extract(item) for column in self.extras)
            else:
                extend_row = lambda item, row: row
            rows = [extend_row(item, row) for item, row in item_rows]
            placeholders = ", ".join("?" * len(rows[0]))
            db.execute(f"INSERT INTO {self.name} VALUES({placeholders})", rows)

    @staticmethod
    def column_schema(columns: list[ColumnDef]) -> str:
        return ", ".join(f"{c.name} {c._sqltype}" for c in columns)


class TableFromCode(Table):
    """A table created from Python code, not from a user config file."""

    def __init__(self, table_def: TableDef, extender: Optional[ExtendTable]):
        """
        :param table_def: a TableDef from the @table decorator
        :param extender: an ExtendTable object from the extend: section of a user config file
        """
        impl = table_def.cls()
        schema = impl.schema
        if extender:
            schema += ", " + Table.column_schema(extender.columns)
            extras = extender.columns
        else:
            extras = []
        super().__init__(table_def.name, table_def.resource, schema, extras)
        self.impl = impl

    def make_rows(self, kube_data: dict) -> list[tuple[dict, tuple]]:
        """Delegate to the user-defined table implementation."""
        return self.impl.make_rows(kube_data)


class TableFromConfig(Table):
    """A table created from a create: section in a user config file, rather than in Python"""

    def __init__(self, name: str, creator: CreateTable, extender: Optional[ExtendTable]):
        """
        :param name: the table name, e.g. "pods"
        :param creator: a CreateTable object from the create: section of a user config file
        :param extender: an ExtendTable object from the extend: section of a user config file
        """
        if creator.row_source is None:
            self.itemizer = lambda data: data["items"]
        else:
            self.itemizer = lambda data: self._itemize(creator.row_source, data)
        schema = Table.column_schema(creator.columns)
        extras = creator.columns
        if extender:
            schema += ", " + Table.column_schema(extender.columns)
            extras += extender.columns
        super().__init__(name, creator.resource, schema, extras)
        self.row_source = creator.row_source

    def make_rows(self, kube_data: dict) -> list[tuple[dict, tuple]]:
        """
        Itemize the data according to the configuration, but return empty rows; all the
        columns will be added by Table.build.
        """
        if self.row_source is not None:
            items = self._itemize(self.row_source, kube_data)
        else:
            items = kube_data["items"]
        return [(item, tuple()) for item in items]

    def _itemize(self, row_source: list[str], kube_data:dict) -> list[dict]:
        """
        Given a row_source like
          row_source:
            - items
            - spec.taints
        Iterate through each level of the source spec, marking object parents, and generating
        successive row values
        """
        items = [kube_data]
        for source in row_source:
            try:
                finder = jmespath.compile(source)
            except jmespath.exceptions.ParseError as e:
                fail(f"invalid row_source {source} for {self.name} table", e)
            new_items = []
            for item in items:
                found = finder.search(item)
                if isinstance(found, list):
                    for child in found:
                        set_parent(child, item)
                        new_items.append(child)
                elif found is not None:
                    set_parent(found, item)
                    new_items.append(found)
            items = new_items
        return items
