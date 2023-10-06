
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import re
import sys
from threading import Lock

import arrow
from tabulate import tabulate

from .jobs import add_jobs
from .jross import SqliteDb, run
from .pods import add_pods
from .nodes import add_nodes
from .utils import add_custom_functions, to_age, KubeConfig
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

    db = SqliteDb()
    db_lock = Lock()
    add_custom_functions(db.conn)

    # Determine which tables are needed for the query
    table_names = set(re.findall(r"(?<=from|join)\s+(\w+)", args.sql.replace("\n", " "), re.IGNORECASE))
    bad_names = table_names.difference(["pods", "jobs", "nodes", "workflows"])
    if bad_names:
        sys.exit(f"Not available for query: {bad_names}")

    # Fetch from K8S in parallel, and add to SQLite thread-safely
    def fetch(table_name):
        data = _get_k8s_objects(table_name, context, update)
        with db_lock:
            globals()[f"add_{table_name}"](db, data)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for _ in pool.map(fetch, table_names):
            pass

    rows = db.query(args.sql)
    print(tabulate(rows, tablefmt="plain", floatfmt=".4g"))
    # now print them with floating-point numbers truncated to two decimal places
    # print(tabulate(rows, tablefmt="plain", floatfmt=".2f"))

def _get_k8s_objects(table_name, context_name, update_cache):
    """
    Fetch Kubernetes objects either via the API or from our cache
    :param table_name: e.g. "pods", "nodes", "jobs" etc..
    :param context_name: a Kubernetes context name from .kube/config
    :param update_cache: how to consult the cache, one of ALWAYS, CHECK, NEVER
    :return: raw JSON objects as output by "kubectl get {table_name}"
    """
    cache_dir = CACHE / context_name
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / f"{table_name}.json"
    if update_cache == NEVER:
        run_kubectl = False
    elif update_cache == ALWAYS or not cache_file.exists():
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
        sys.exit(f"No cache file exists for {table_name} table")
    return json.loads(cache_file.read_text())