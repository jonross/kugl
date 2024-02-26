
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

from .cluster import Cluster
from .config import KConfig
from .constants import ALWAYS, CHECK, NEVER
from .jross import SqliteDb, run
from .jobs import add_jobs
from .nodes import add_nodes, add_node_taints
from .pods import add_pods
from .utils import add_custom_functions, to_age, KubeConfig, fail
from .workflows import add_workflows

def main():
    ap = ArgumentParser()
    ap.add_argument("-n", "--no_update", default=False, action="store_true")
    ap.add_argument("-u", "--update", default=False, action="store_true")
    ap.add_argument("-v", "--verbose", default=False, action="store_true")
    ap.add_argument("sql")
    args = ap.parse_args(sys.argv[1:])
    try:
        _main(args)
    except Exception as e:
        if args.verbose:
            raise
        print(e, file=sys.stderr)
        sys.exit(1)


def _main(args):
    if args.update and args.no_update:
        fail("Cannot specify both --no-update and --update")

    cluster = Cluster(KubeConfig().current_context(),
                      ALWAYS if args.update else NEVER if args.no_update else CHECK)
    kd = KubeData(cluster)
    kc = KConfig()

    if " " not in args.sql:
        args.sql = kc.canned_query(args.sql)

    rows, headers = kd.query(kc, args.sql)
    # %g is susceptible to outputting scientific notation, which we don't want.
    # but %f always outputs trailing zeros, which we also don't want.
    # So turn every value x in each row into an int if x == float(int(x))
    truncate = lambda x: int(x) if isinstance(x, float) and x == float(int(x)) else x
    rows = [[truncate(x) for x in row] for row in rows]
    print(tabulate(rows, tablefmt="plain", floatfmt=".1f", headers=headers))


class KubeData:

    def __init__(self, cluster: Cluster, data: dict | None = None):
        """
        :param update_cache: how to consult the cache, one of ALWAYS, CHECK, NEVER
        :param context_name: a Kubernetes context name from .kube/config
        """
        self.data = data or {}
        self.cluster = cluster
        self.db = SqliteDb()
        self.db_lock = Lock()
        add_custom_functions(self.db.conn)

    def query(self, config, kql):

        # Correlate queryable tables with object types needed from K8S.
        Table = co.namedtuple("Table", ["name", "needs", "builders"])
        table_needs = {t.name: t for t in [
            Table("pods", ["pods"], [add_pods]),
            Table("jobs", ["jobs"], [add_jobs]),
            Table("nodes", ["nodes"], [add_nodes]),
            Table("workflows", ["workflows"], [add_workflows]),
            Table("node_taints", ["nodes"], [add_node_taints]),
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
        fetch_types = fn.lflatten(table_needs[table_name].needs for table_name in table_names)
        def fetch(object_type):
            if object_type not in self.data:
                self.data[object_type] = self.cluster.get_objects(object_type)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in pool.map(fetch, fetch_types):
                pass

        # Create tables in SQLite
        called_builders = set()
        for table_name in table_names:
            for builder in table_needs[table_name].builders:
                if builder not in called_builders:
                    called_builders.add(builder)
                    builder(self.db, config, self.data)

        column_names = []
        rows = self.db.query(kql, names=column_names)
        return rows, column_names
