import funcy as fn

from .dbmodel import Column, Table
from .constants import MAIN_CONTAINERS
from .utils import K8SObjectHelper, Resources, MyConfig


class PodsTable(Table):

    NAME = "pods"
    RESOURCE_KIND = "pods"
    SCHEMA = """
        name TEXT,
        namespace TEXT,
        node_name TEXT,
        command TEXT,
        status TEXT,
        cpu_req REAL,
        gpu_req REAL,
        mem_req INTEGER,
        cpu_lim REAL,
        gpu_lim REAL,
        mem_lim INTEGER
    """

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            pod.name,
            pod.namespace,
            pod.node_name,
            pod.command,
            pod.status,
            *pod.resources("requests").as_tuple(),
            *pod.resources("limits").as_tuple(),
        ) for pod in map(PodHelper, kube_data)]


class PodHelper(K8SObjectHelper):

    @property
    def node_name(self):
        return self["spec"].get("nodeName")

    @property
    def command(self):
        return " ".join((self.main or {}).get("command", []))

    @property
    def status(self):
        # FIXME: use actual logic from kubectl
        if "deletionTimestamp" in self["metadata"]:
            return "Terminating"
        for status in self["status"].get("containerStatuses", []):
            for condition in "waiting", "terminated":
                reason = status["state"].get(condition, {}).get("reason")
                if reason is not None:
                    return reason
        return self["status"].get("reason") or self["status"]["phase"]

    @property
    def containers(self):
        """Return the containers in the pod, if any, else an empty list."""
        return self["spec"].get("containers", [])

    @property
    def main(self):
        """
        Return the main container in the pod, if any, defined as the first container with a name
        of "main" or "notebook".
        """
        return fn.first(fn.filter(lambda c: c["name"] in MAIN_CONTAINERS, self.containers))

    def resources(self, tag):
        return sum(Resources.extract(c["resources"].get(tag)) for c in self.containers)