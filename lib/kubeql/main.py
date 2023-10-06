
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import sys

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
    _, context, _ = run(["kubectl", "config", "current-context"])
    context = KubeConfig().current_context()
    with ThreadPoolExecutor(max_workers=8) as pool:
        pods, jobs, nodes, workflows = pool.map(lambda x: _get_k8s_objects(x, context, update),
                                                ["pods", "jobs", "nodes", "workflows"])
    db = SqliteDb()
    add_custom_functions(db.conn)
    add_pods(db, pods)
    add_jobs(db, jobs)
    add_nodes(db, nodes)
    add_workflows(db, workflows)
    rows = db.query(args.sql)
    print(tabulate(rows, tablefmt="plain"))

def _get_k8s_objects(kind, context, cache_how):
    """
    Fetch Kubernetes objects either via the API or from our cache
    :param kind: e.g. "pods", "nodes", "jobs" etc..
    :param context: a Kubernetes context name
    :param cache_how: how to consult the cache, one of ALWAYS, CHECK, NEVER
    :return: raw JSON objects as output by "kubectl get {kind}"
    """
    cache_dir = CACHE / context
    cache_dir.mkdir(exist_ok=True)
    data = cache_dir / f"{kind}.json"
    if cache_how == NEVER:
        regen = False
    elif cache_how == ALWAYS or not data.exists():
        regen = True
    elif to_age(data.stat().st_mtime) > timedelta(minutes=10):
        regen = True
    else:
        regen = False
    if regen:
        all_ns = [] if kind == "nodes" else ["--all-namespaces"]
        _, out, _= run(["kubectl", "get", kind, *all_ns, "-o", "json"])
        data.write_text(out)
    if not data.exists():
        sys.exit(f"No data for {kind} table")
    return json.loads(data.read_text())