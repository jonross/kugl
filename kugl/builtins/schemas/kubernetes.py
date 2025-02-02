"""
Built-in table definitions for Kubernetes.

NOTE: This is not a good example of how to write user-defined tables.
FIXME: Remove references to non-API imports.
FIXME: Don't use ArgumentParser in the API.
"""
import json
import os
from argparse import ArgumentParser
from threading import Thread

from pydantic import model_validator

from ..helpers import Limits, ItemHelper, PodHelper, JobHelper
from kugl.api import table, fail, resource, run, parse_utc, Resource, column
from kugl.util import WHITESPACE_RE, kube_context


@resource("kubernetes", schema_defaults=["kubernetes"])
class KubernetesResource(Resource):

    namespaced: bool
    _all_ns: bool
    _ns: str

    @model_validator(mode="after")
    @classmethod
    def set_cacheable(cls, resource: "KubernetesResource") -> "KubernetesResource":
        # Kubernetes resources are cacheable by default, for reasons outlined in README.md
        if resource.cacheable is None:
            resource.cacheable = True
        return resource

    @classmethod
    def add_cli_options(cls, ap: ArgumentParser):
        ap.add_argument("-a", "--all-namespaces", default=False, action="store_true")
        ap.add_argument("-n", "--namespace", type=str)

    def handle_cli_options(self, args):
        if args.all_namespaces and args.namespace:
            fail("Cannot use both -a/--all-namespaces and -n/--namespace")
        if args.all_namespaces:
            self._ns = "__all"
            self._all_ns = True
        else:
            self._ns = args.namespace or "default"
            self._all_ns = False

    def cache_path(self) -> str:
        return f"{kube_context()}/{self._ns}.{self.name}.json"

    def get_objects(self) -> dict:
        """Fetch resources from Kubernetes using kubectl.

        :return: JSON as output by "kubectl get {self.name} -o json"
        """
        unit_testing = "KUGL_UNIT_TESTING" in os.environ
        namespace_flag = ["--all-namespaces"] if self._all_ns else ["-n", self._ns]
        if self.name == "pods":
            pod_statuses = {}
            # Kick off a thread to get pod statuses
            def _fetch():
                _, output, _ = run(["kubectl", "get", "pods", *namespace_flag])
                pod_statuses.update(self._pod_status_from_pod_list(output))
            status_thread = Thread(target=_fetch, daemon=True)
            status_thread.start()
            # In unit tests, wait for pod status here so the log order is deterministic.
            if unit_testing:
                status_thread.join()
        if self.namespaced:
            _, output, _ = run(["kubectl", "get", self.name, *namespace_flag, "-o", "json"])
        else:
            _, output, _ = run(["kubectl", "get", self.name, "-o", "json"])
        data = json.loads(output)
        if self.name == "pods":
            # Add pod status to pods
            if not unit_testing:
                status_thread.join()
            def pod_with_updated_status(pod):
                metadata = pod["metadata"]
                status = pod_statuses.get(f"{metadata['namespace']}/{metadata['name']}")
                if status:
                    pod["kubectl_status"] = status
                    return pod
                return None
            data["items"] = list(filter(None, map(pod_with_updated_status, data["items"])))
        return data

    def _pod_status_from_pod_list(self, output) -> dict[str, str]:
        """
        Convert the tabular output of 'kubectl get pods' to JSON.
        :return: a dict mapping "namespace/name" to status
        """
        rows = [WHITESPACE_RE.split(line.strip()) for line in output.strip().split("\n")]
        if len(rows) < 2:
            return {}
        header, rows = rows[0], rows[1:]
        name_index = header.index("NAME")
        status_index = header.index("STATUS")
        # It would be nice if 'kubectl get pods' printed the UID, but it doesn't, so use
        # "namespace/name" as the key.  (Can't use a tuple since this has to be JSON-dumped.)
        if self._all_ns:
            namespace_index = header.index("NAMESPACE")
            return {f"{row[namespace_index]}/{row[name_index]}": row[status_index] for row in rows}
        else:
            return {f"{self._ns}/{row[name_index]}": row[status_index] for row in rows}


@table(schema="kubernetes", name="nodes", resource="nodes")
class NodesTable:

    _COLUMNS = [
        column("name", "TEXT", "node name, from metadata.name"),
        column("uid", "TEXT", "node UID, from metadata.uid"),
        column("cpu_alloc", "REAL", "allocatable CPUs, from status.allocatable"),
        column("gpu_alloc", "REAL", "allocatable GPUs, or null if none"),
        column("mem_alloc", "INTEGER", "allocatable memory, in bytes"),
        column("cpu_cap", "REAL", "CPU capacity, from status.capacity"),
        column("gpu_cap", "REAL", "GPU capacity, or null if none"),
        column("mem_cap", "INTEGER", "memory capacity, in bytes"),
    ]

    def columns(self):
        return self._COLUMNS

    def make_rows(self, context) -> list[tuple[dict, tuple]]:
        for item in context.data["items"]:
            node = ItemHelper(item)
            yield item, (
                node.name,
                node.metadata.get("uid"),
                *Limits.extract(node["status"]["allocatable"], debug=context.debug).as_tuple(),
                *Limits.extract(node["status"]["capacity"], debug=context.debug).as_tuple(),
            )


@table(schema="kubernetes", name="pods", resource="pods")
class PodsTable:

    _COLUMNS = [
        column("name", "TEXT", "pod name, from metadata.name"),
        column("uid", "TEXT", "pod UID, from metadata.uid"),
        column("namespace", "TEXT", "pod namespace, from metadata.namespace"),
        column("node_name", "TEXT", "node name, from spec.nodeName, or null"),
        column("creation_ts", "INTEGER", "creation timestamp in epoch seconds, from metadata.creationTimestamp"),
        column("deletion_ts", "INTEGER", "deletion timestamp in epoch seconds, from metadata.deletionTimestamp"),
        column("is_daemon", "INTEGER", "1 if a daemonset pod, 0 otherwise"),
        column("command", "TEXT", "command from main container"),
        column("phase", "TEXT", "pod phase, from status.phase"),
        column("status", "TEXT", "pod STATUS as output by 'kubectl get pod'"),
        column("cpu_req", "REAL", "sum of CPUs requested across containers"),
        column("gpu_req", "REAL", "sum of GPUs requested, or null"),
        column("mem_req", "INTEGER", "sum of memory requested, in bytes"),
        column("cpu_lim", "REAL", "CPU limit, or null"),
        column("gpu_lim", "REAL", "GPU limit, or null"),
        column("mem_lim", "INTEGER", "memory limit, or null"),
    ]

    def columns(self):
        return self._COLUMNS

    def make_rows(self, context) -> list[tuple[dict, tuple]]:
        for item in context.data["items"]:
            pod = PodHelper(item)
            yield item, (
                pod.name,
                pod.metadata.get("uid"),
                pod.namespace,
                pod["spec"].get("nodeName"),
                parse_utc(pod.metadata["creationTimestamp"]),
                parse_utc(pod.metadata.get("deletionTimestamp")),
                1 if pod.is_daemon else 0,
                pod.command,
                pod["status"]["phase"],
                pod["kubectl_status"],
                *pod.resources("requests", debug=context.debug).as_tuple(),
                *pod.resources("limits", debug=context.debug).as_tuple(),
            )


@table(schema="kubernetes", name="jobs", resource="jobs")
class JobsTable:

    _COLUMNS = [
        column("name", "TEXT", "job name, from metadata.name"),
        column("uid", "TEXT", "job UID, from metadata.name"),
        column("namespace", "TEXT", "job namespace,from metadata.namespace"),
        column("status", "TEXT", "job status, one of 'Running', 'Complete', 'Suspended', 'Failed', 'Unknown'"),
        column("cpu_req", "REAL", "sum of CPUs requested across containers"),
        column("gpu_req", "REAL", "sum of GPUs requested, or null"),
        column("mem_req", "INTEGER", "sum of memory requested, in bytes"),
        column("cpu_lim", "REAL", "CPU limit, or null"),
        column("gpu_lim", "REAL", "GPU limit, or null"),
        column("mem_lim", "INTEGER", "memory limit, or null"),
    ]

    def columns(self):
        return self._COLUMNS

    def make_rows(self, context) -> list[tuple[dict, tuple]]:
        for item in context.data["items"]:
            job = JobHelper(item)
            yield item, (
                job.name,
                job.metadata.get("uid"),
                job.namespace,
                job.status,
                *job.resources("requests", debug=context.debug).as_tuple(),
                *job.resources("limits", debug=context.debug).as_tuple(),
            )


class LabelsTable:
    """Base class for all built-in label tables; subclasses need only define UID_FIELD."""

    def columns(self):
        return [
            column(self.UID_FIELD, "TEXT", "object UID, from metadata.uid"),
            column("key", "TEXT", "label key"),
            column("value", "TEXT", "label value"),
        ]

    def make_rows(self, context) -> list[tuple[dict, tuple]]:
        for item in context.data["items"]:
            thing = ItemHelper(item)
            for key, value in thing.labels.items():
                yield item, (thing.metadata.get("uid"), key, value)


@table(schema="kubernetes", name="node_labels", resource="nodes")
class NodeLabelsTable(LabelsTable):
    UID_FIELD = "node_uid"


@table(schema="kubernetes", name="pod_labels", resource="pods")
class PodLabelsTable(LabelsTable):
    UID_FIELD = "pod_uid"


@table(schema="kubernetes", name="job_labels", resource="jobs")
class JobLabelsTable(LabelsTable):
    UID_FIELD = "job_uid"