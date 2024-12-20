"""
Built-in table definitions for Kubernetes.
"""

from .helpers import Limits, ItemHelper, PodHelper, JobHelper
from kugel.util.time import parse_utc
from .registry import domain, table


@domain("kubernetes")
class KubernetesData:
    pass


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