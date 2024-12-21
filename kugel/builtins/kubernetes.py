"""
Built-in table definitions for Kubernetes.

NOTE: This is not a good example of how to write user-defined tables.
FIXME: Remove references to non-API imports.
"""
import json
from argparse import ArgumentParser

from .helpers import Limits, ItemHelper, PodHelper, JobHelper
from kugel.api import domain, table, fail
from kugel.impl.config import Config
from kugel.util import parse_utc, run, WHITESPACE

# Fake namespace if "--all-namespaces" option is used
ALL_NAMESPACE = "__all"


@domain("kubernetes")
class KubernetesData:

    def add_cli_options(self, ap: ArgumentParser):
        ap.add_argument("-a", "--all-namespaces", default=False, action="store_true")
        ap.add_argument("-n", "--namespace", type=str)

    def handle_cli_options(self, args):
        if args.cache and args.update:
            fail("Cannot use both -c/--cache and -u/--update")
        if args.all_namespaces and args.namespace:
            fail("Cannot use both -a/--all-namespaces and -n/--namespace")
        self.namespace = ALL_NAMESPACE if args.all_namespaces else args.namespace or "default"

    def get_objects(self, kind: str, config: Config)-> dict:
        """Fetch resources from Kubernetes using kubectl.

        :param kind: Kubernetes resource type e.g. "pods"
        :return: JSON as output by "kubectl get {kind} -o json"
        """
        namespace_flag = ["--all-namespaces"] if self.namespace == ALL_NAMESPACE else ["-n", self.namespace]
        is_namespaced = config.resources[kind].namespaced
        if not is_namespaced:
            _, output, _ = run(["kubectl", "get", kind, "-o", "json"])
            return json.loads(output)
        elif kind == "pod_statuses":
            _, output, _= run(["kubectl", "get", "pods", *namespace_flag])
            return self._pod_status_from_pod_list(output)
        else:
            _, output, _= run(["kubectl", "get", kind, *namespace_flag, "-o", "json"])
            return json.loads(output)

    def _pod_status_from_pod_list(self, output):
        """Convert the tabular output of 'kubectl get pods' to JSON."""
        rows = [WHITESPACE.split(line.strip()) for line in output.strip().split("\n")]
        if len(rows) < 2:
            return {}
        header, rows = rows[0], rows[1:]
        name_index = header.index("NAME")
        status_index = header.index("STATUS")
        if name_index is None or status_index is None:
            raise ValueError("Can't find NAME and STATUS columns in 'kubectl get pods' output")
        return {row[name_index]: row[status_index] for row in rows}


@table(domain="kubernetes", name="nodes", resource="nodes")
class NodesTable:

    @property
    def schema(self):
        return """
            name TEXT,
            instance_type TEXT,
            cpu_alloc REAL,
            gpu_alloc REAL,
            mem_alloc INTEGER,
            cpu_cap REAL,
            gpu_cap REAL,
            mem_cap INTEGER
        """

    def make_rows(self, kube_data: dict) -> list[tuple[dict, tuple]]:
        for item in kube_data["items"]:
            node = ItemHelper(item)
            yield item, (
                node.name,
                node.label("node.kubernetes.io/instance-type") or node.label("beta.kubernetes.io/instance-type"),
                *Limits.extract(node["status"]["allocatable"]).as_tuple(),
                *Limits.extract(node["status"]["capacity"]).as_tuple(),
            )


@table(domain="kubernetes", name="pods", resource="pods")
class PodsTable:

    @property
    def schema(self):
        return """
            name TEXT,
            is_daemon INTEGER,
            namespace TEXT,
            node_name TEXT,
            creation_ts INTEGER,
            command TEXT,
            status TEXT,
            cpu_req REAL,
            gpu_req REAL,
            mem_req INTEGER,
            cpu_lim REAL,
            gpu_lim REAL,
            mem_lim INTEGER
        """

    def make_rows(self, kube_data: dict) -> list[tuple[dict, tuple]]:
        for item in kube_data["items"]:
            pod = PodHelper(item)
            yield item, (
                pod.name,
                1 if pod.is_daemon else 0,
                pod.namespace,
                pod["spec"].get("nodeName"),
                parse_utc(pod.metadata["creationTimestamp"]),
                pod.command,
                pod["kubectl_status"],
                *pod.resources("requests").as_tuple(),
                *pod.resources("limits").as_tuple(),
            )


@table(domain="kubernetes", name="jobs", resource="jobs")
class JobsTable:

    @property
    def schema(self):
        return """
            name TEXT,
            namespace TEXT,
            status TEXT,
            cpu_req REAL,
            gpu_req REAL,
            mem_req INTEGER,
            cpu_lim REAL,
            gpu_lim REAL,
            mem_lim INTEGER
        """

    def make_rows(self, kube_data: dict) -> list[tuple[dict, tuple]]:
        for item in kube_data["items"]:
            job = JobHelper(item)
            yield item, (
                job.name,
                job.namespace,
                job.status,
                *job.resources("requests").as_tuple(),
                *job.resources("limits").as_tuple(),
            )