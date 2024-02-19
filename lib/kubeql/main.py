
from argparse import ArgumentParser
import collections as co
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import funcy as fn
import json
from pathlib import Path
import re
import sys
from threading import Lock

from tabulate import tabulate
import yaml

from .jross import SqliteDb, run
from .utils import add_custom_functions, to_age, KubeConfig

from .jobs import add_jobs
from .nodes import add_nodes, add_node_taints, add_node_load
from .pods import add_pods
from .workflows import add_workflows

ALWAYS, CHECK, NEVER = 1, 2, 3
CACHE = Path.home() / ".kubeql"

def main():
    ap = ArgumentParser()
    ap.add_argument("-n", "--no_update", default=False, action="store_true")
    ap.add_argument("-u", "--update", default=False, action="store_true")
    ap.add_argument("sql")
    args = ap.parse_args()
    if args.update and args.no_update:
        sys.exit("Cannot specify both --no-update and --update")

    update = ALWAYS if args.update else NEVER if args.no_update else CHECK
    context = KubeConfig().current_context()
    kd = KubeData(CACHE, update, context)

    # Check for a predefined query
    config_file = CACHE / "canned.yaml"
    if config_file.exists():
        config = yaml.safe_load(config_file.read_text())
        if args.sql in config:
            args.sql = config[args.sql]

    rows, headers = kd.query(args.sql)
    # %g is susceptible to outputting scientific notation, which we don't want.
    # but %f always outputs trailing zeros, which we also don't want.
    # So turn every value x in each row into an int if x == float(int(x))
    truncate = lambda x: int(x) if isinstance(x, float) and x == float(int(x)) else x
    rows = [[truncate(x) for x in row] for row in rows]
    print(tabulate(rows, tablefmt="plain", floatfmt=".1f", headers=headers))


class KubeData:

    def __init__(self, cache_dir: Path, update_cache: bool, context_name: str):
        """
        :param update_cache: how to consult the cache, one of ALWAYS, CHECK, NEVER
        :param context_name: a Kubernetes context name from .kube/config
        """
        self.cache_dir = cache_dir
        self.update_cache = update_cache
        self.context_name = context_name
        self.db = SqliteDb()
        self.db_lock = Lock()
        add_custom_functions(self.db.conn)

    def get_objects(self, table_name):
        """
        Fetch Kubernetes objects either via the API or from our cache
        :param table_name: e.g. "pods", "nodes", "jobs" etc..
        :return: raw JSON objects as output by "kubectl get {table_name}"
        """
        cache_dir = self.cache_dir / self.context_name
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / f"{table_name}.json"
        if self.update_cache == NEVER:
            run_kubectl = False
        elif self.update_cache == ALWAYS or not cache_file.exists():
            run_kubectl = True
        elif to_age(cache_file.stat().st_mtime) > timedelta(minutes=10):
            run_kubectl = True
        else:
            run_kubectl = False
        if run_kubectl:
            all_ns = [] if table_name == "nodes" else ["--all-namespaces"]
            _, output, _= run(["kubectl", "get", table_name, *all_ns, "-o", "json"])
            cache_file.write_text(output)
        if not cache_file.exists():
            # TODO: throw exception instead, use backstop in main()
            sys.exit(f"No cache file exists for {table_name} table")
        return json.loads(cache_file.read_text())

    def query(self, kql):

        # Correlate queryable tables with object types needed from K8S.
        Table = co.namedtuple("Table", ["name", "needs", "builders"])
        table_needs = {t.name: t for t in [
            Table("pods", ["pods"], [add_pods]),
            Table("jobs", ["jobs"], [add_jobs]),
            Table("nodes", ["nodes"], [add_nodes]),
            Table("workflows", ["workflows"], [add_workflows]),
            Table("node_taints", ["nodes"], [add_node_taints]),
            Table("node_load", ["pods"], [add_pods, add_node_load]),
        ]}

        # Determine which tables are needed for the query
        kql = kql.replace("\n", " ")
        table_names = set(re.findall(r"(?<=from|join)\s+(\w+)", kql, re.IGNORECASE))
        cte_names = set(re.findall(r"(?<=with)\s+(\w+)\s+(?=as)", kql, re.IGNORECASE))
        table_names = table_names.difference(cte_names)
        bad_names = table_names.difference(table_needs.keys())
        if bad_names:
            sys.exit(f"Not available for query: {bad_names}")

        # Fetch required object types from K8S in parallel.
        objects = {}
        fetch_types = fn.lflatten(table_needs[table_name].needs for table_name in table_names)
        def fetch(object_type):
            objects[object_type] = self.get_objects(object_type)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in pool.map(fetch, fetch_types):
                pass

        # Create tables in SQLite
        called_builders = set()
        for table_name in table_names:
            for builder in table_needs[table_name].builders:
                if builder not in called_builders:
                    called_builders.add(builder)
                    builder(self.db, objects)

        column_names = []
        rows = self.db.query(kql, names=column_names)
        return rows, column_names
