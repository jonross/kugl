
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
import re
import sys
from threading import Lock

from tabulate import tabulate

from .cluster import Cluster
from .constants import ALWAYS, CHECK, NEVER
from .jross import SqliteDb, run
from .tables import *
from .utils import add_custom_functions, to_age, KubeConfig, fail, MyConfig

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
    kc = MyConfig()

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

        all_tables = [PodsTable, JobsTable, NodesTable, NodeTaintsTable, WorkflowsTable]

        # Determine which tables are needed for the query
        kql = kql.replace("\n", " ")
        table_names = (set(re.findall(r"(?<=from|join)\s+(\w+)", kql, re.IGNORECASE)) -
                       set(re.findall(r"(?<=with)\s+(\w+)\s+(?=as)", kql, re.IGNORECASE)))
        bad_names = table_names - {t.NAME for t in all_tables}
        if bad_names:
            sys.exit(f"Not available for query: {', '.join(bad_names)}")

        # Fetch required object types from K8S in parallel.
        tables_used = [t() for t in all_tables if t.NAME in table_names]
        resources_used = {t.RESOURCE_KIND for t in tables_used}
        def fetch(kind):
            if kind not in self.data:
                self.data[kind] = self.cluster.get_objects(kind)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in pool.map(fetch, resources_used):
                pass

        # Create tables in SQLite
        for t in tables_used:
            t.create(self.db, config, self.data[t.NAME])

        column_names = []
        rows = self.db.query(kql, names=column_names)
        return rows, column_names
