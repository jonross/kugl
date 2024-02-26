"""
Interface to kubectl / the Kubernetes API + a cache of their responses.
"""

from datetime import timedelta
import json
from pathlib import Path
from typing import Literal
import sys

from .constants import ALWAYS, CHECK, NEVER
from .constants import CACHE, RESOURCE_KINDS
from .jross import run
from .utils import fail, to_age


class Cluster:

    def __init__(self, context_name: str, update_cache: Literal[ALWAYS, CHECK, NEVER],
                 cache_dir: Path = CACHE):
        self.context_name = context_name
        self.update_cache = update_cache
        self.cache_dir = cache_dir

    def get_objects(self, kind: RESOURCE_KINDS)-> dict:
        """
        Fetch Kubernetes objects either via the API or from our cache
        :param kind: known K8S resource kind e.g. "pods", "nodes", "jobs" etc..
        :return: raw JSON objects as output by "kubectl get {kind}"
        """
        cache_dir = self.cache_dir / self.context_name
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / f"{kind}.json"
        if self.update_cache == NEVER:
            run_kubectl = False
        elif self.update_cache == ALWAYS or not cache_file.exists():
            run_kubectl = True
        elif to_age(cache_file.stat().st_mtime) > timedelta(minutes=10):
            run_kubectl = True
        else:
            run_kubectl = False
        if run_kubectl:
            all_ns = [] if kind == "nodes" else ["--all-namespaces"]
            _, output, _= run(["kubectl", "get", kind, *all_ns, "-o", "json"])
            cache_file.write_text(output)
        if not cache_file.exists():
            fail(f"Internal error: no cache file exists for {kind} table")
        return json.loads(cache_file.read_text())