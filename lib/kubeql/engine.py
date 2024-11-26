import time
from datetime import datetime
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
from threading import Lock
from typing import Tuple, Set, Optional

from tabulate import tabulate

from kubeql.constants import CACHE_EXPIRATION, CacheFlag, ALL_NAMESPACE, WHITESPACE, ALWAYS_UPDATE, NEVER_UPDATE
from kubeql.jross import run, SqliteDb
from kubeql.tables import PodsTable, JobsTable, NodesTable, NodeTaintsTable, WorkflowsTable
from kubeql.utils import MyConfig, fail, add_custom_functions

Query = namedtuple("Query", ["sql", "namespace", "cache_flag"])


class Engine:

    def __init__(self, config: MyConfig, context_name: str):
        self.config = config
        self.context_name = context_name
        self.cache = DataCache(self.config.cache_dir / self.context_name)
        self.data = {}
        self.db = SqliteDb()
        self.db_lock = Lock()
        add_custom_functions(self.db.conn)

    def query_and_format(self, query: Query):
        rows, headers = self.query(query)
        # %g is susceptible to outputting scientific notation, which we don't want.
        # but %f always outputs trailing zeros, which we also don't want.
        # So turn every value x in each row into an int if x == float(int(x))
        truncate = lambda x: int(x) if isinstance(x, float) and x == float(int(x)) else x
        rows = [[truncate(x) for x in row] for row in rows]
        return tabulate(rows, tablefmt="plain", floatfmt=".1f", headers=headers)

    def query(self, query: Query):

        table_classes = [PodsTable, JobsTable, NodesTable, NodeTaintsTable, WorkflowsTable]

        # Determine which tables are needed for the query by looking for symmbols that follow
        # FROM, JOIN, and WITH
        kql = query.sql.replace("\n", " ")
        table_names = (set(re.findall(r"(?<=from|join)\s+(\w+)", kql, re.IGNORECASE)) -
                       set(re.findall(r"(?<=with)\s+(\w+)\s+(?=as)", kql, re.IGNORECASE)))
        bad_names = table_names - {c.NAME for c in table_classes}
        if bad_names:
            fail(f"Not available for query: {', '.join(bad_names)}")

        # Based on the tables used, what resources are needed from Kubernetes
        tables_used = [c() for c in table_classes if c.NAME in table_names]
        resources_used = {t.RESOURCE_KIND for t in tables_used}
        if "pods" in resources_used:
            # This is fake, _get_objects knows to get it via "kubectl get pods" not as JSON
            resources_used.add("pod_statuses")

        # Identify what to fetch vs what's stale or expire.
        resources_fetched, max_stale_age = self.cache.advise_refresh(query.namespace, resources_used, query.cache_flag)
        if max_stale_age is not None:
            print(f"(Data may be up to {max_stale_age} seconds old.)", file=sys.stderr)
            time.sleep(0.5)

        # Retrieve resource data in parallel.  If fetching from Kubernetes, update the cache;
        # otherwise just read from the cache.
        def fetch(kind):
            try:
                if kind in resources_fetched:
                    self.data[kind] = self._get_objects(kind, query)
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
        for t in tables_used:
            t.create(self.db, self.config, self.data[t.NAME])

        column_names = []
        rows = self.db.query(kql, names=column_names)
        return rows, column_names

    def _get_objects(self, kind: str, query: Query)-> dict:
        """
        TODO: update comment

        Fetch Kubernetes objects either via the API or from our cache.
        Special handling if kind is "pod_statuses" -- return a dict mapping pod name to
        status as shown by "kubectl get pods".

        :param kind: known K8S resource kind e.g. "pods", "nodes", "jobs" etc..
        :return: raw JSON objects as output by "kubectl get {kind}"
        """
        namespace_flag = ["--all-namespaces"] if query.namespace == ALL_NAMESPACE else ["-n", query.namespace]
        if kind == "nodes":
            _, output, _ = run(["kubectl", "get", kind, "-o", "json"])
            return json.loads(output)
        elif kind == "pod_statuses":
            _, output, _= run(["kubectl", "get", "pods", *namespace_flag])
            return self._pod_status_from_pod_list(output)
        else:
            _, output, _= run(["kubectl", "get", kind, *namespace_flag, "-o", "json"])
            return json.loads(output)

    def _pod_status_from_pod_list(self, output):
        rows = [WHITESPACE.split(line.strip()) for line in output.strip().split("\n")]
        header, rows = rows[0], rows[1:]
        name_index = header.index("NAME")
        status_index = header.index("STATUS")
        if name_index is None or status_index is None:
            raise ValueError("Can't find NAME and STATUS columns in 'kubectl get pods' output")
        return {row[name_index]: row[status_index] for row in rows}


class DataCache:
    """
    Manage the cached JSON data we get from Kubectl.
    This is a separate class for ease of unit testing.
    """

    def __init__(self, dir: Path):
        self.dir = dir
        dir.mkdir(parents=True, exist_ok=True)

    def advise_refresh(self, namespace: str, kinds: Set[str], flag: CacheFlag) -> Tuple[Set[str], int]:
        if flag == ALWAYS_UPDATE:
            # Refresh everything and don't issue a "stale data" warning
            return kinds, None
        # Find what's expired or missing
        cache_ages = {kind: self.age(self.cache_path(namespace, kind)) for kind in kinds}
        expired = {kind for kind, age in cache_ages.items() if age is not None and age >= CACHE_EXPIRATION}
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
        """
        Return the age of a file in seconds, relative to the current time.
        If the file doesn't exist, return None.
        """
        if not path.exists():
            return None
        return int((datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds())
