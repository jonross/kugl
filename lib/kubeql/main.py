
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
from .utils import add_custom_functions, to_age
from .workflows import add_workflows

ALWAYS, CHECK, NEVER = 1, 2, 3
STORAGE = Path.home() / ".kubeql"

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
    context = context.strip()
    with ThreadPoolExecutor(max_workers=8) as pool:
        pods, jobs, nodes, workflows = pool.map(lambda x: fetch(x, context, update),
                                                ["pods", "jobs", "nodes", "workflows"])
    db = SqliteDb()
    add_custom_functions(db.conn)
    add_pods(db, pods)
    add_jobs(db, jobs)
    add_nodes(db, nodes)
    add_workflows(db, workflows)
    rows = db.query(args.sql)
    print(tabulate(rows, tablefmt="plain"))

def fetch(what, context, update):
    dir = STORAGE / context
    dir.mkdir(exist_ok=True)
    data = dir / f"{what}.json"
    if update == NEVER:
        regen = False
    elif update == ALWAYS or not data.exists():
        regen = True
    elif to_age(data.stat().st_mtime) > timedelta(minutes=10):
        regen = True
    else:
        regen = False
    if regen:
        all_ns = [] if what == "nodes" else ["--all-namespaces"]
        _, out, _= run(["kubectl", "get", what, *all_ns, "-o", "json"])
        data.write_text(out)
    if not data.exists():
        sys.exit(f"No data for {what} table")
    return json.loads(data.read_text())