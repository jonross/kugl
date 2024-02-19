"""
Two implementations of a source of Kubernetes JSON data.
One connects to a real cluster; the other is for testing
"""

from datetime import timedelta
import json
from pathlib import Path
import sys

from .jross import run
from .utils import to_age

class RealK8S:

    ALWAYS, CHECK, NEVER = 1, 2, 3

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def get_objects(self, table_name, context_name, update_cache):
        """
        Fetch Kubernetes objects either via the API or from our cache
        :param table_name: e.g. "pods", "nodes", "jobs" etc..
        :param context_name: a Kubernetes context name from .kube/config
        :param update_cache: how to consult the cache, one of ALWAYS, CHECK, NEVER
        :return: raw JSON objects as output by "kubectl get {table_name}"
        """
        cache_dir = self.cache_dir / context_name
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / f"{table_name}.json"
        if update_cache == self.NEVER:
            run_kubectl = False
        elif update_cache == self.ALWAYS or not cache_file.exists():
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
