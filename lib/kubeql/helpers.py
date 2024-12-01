"""
Wrappers to make JSON returned by kubectl easier to work with.
"""

from dataclasses import dataclass

import funcy as fn

from .constants import MAIN_CONTAINERS
from .jross import from_footprint


@dataclass
class Resources:  # TODO: Rename this, it can be confused with resource type e.g. pods
    cpu: float
    gpu: float
    mem: int

    def __add__(self, other):
        return Resources(self.cpu + other.cpu, self.gpu + other.gpu, self.mem + other.mem)

    def __radd__(self, other):
        """Needed to support sum()"""
        return self if other == 0 else self.__add__(other)

    def as_tuple(self):
        return (self.cpu, self.gpu, self.mem)

    @classmethod
    def extract(cls, obj):
        if obj is None:
            return Resources(0, 0, 0)
        cpu = from_footprint(obj.get("cpu", "0"))
        gpu = int(obj.get("nvidia.com/gpu", 0))
        mem = from_footprint(obj.get("memory", "0"))
        return Resources(cpu, gpu, mem)


class ItemHelper:
    """
    Some common code for wrappers on JSON for pods, nodes et cetera
    """

    def __init__(self, obj):
        self.obj = obj
        self.metadata = self.obj.get("metadata", {})
        self.labels = self.metadata.get("labels", {})

    def __getitem__(self, key):
        """Return a key from the object; no default, will error if not present"""
        return self.obj[key]

    @property
    def name(self):
        """Return the name of the object from the metadata, or none if unavailable."""
        return self.metadata.get("name") or self.obj.get("name")

    @property
    def namespace(self):
        """Return the name of the object from the metadata, or none if unavailable."""
        return self.metadata.get("namespace")

    def label(self, name):
        """
        Return one of the labels from the object, or None if it doesn't have that label.
        """
        return self.labels.get(name)


class PodHelper(ItemHelper):

    @property
    def command(self):
        return " ".join((self.main or {}).get("command", []))

    @property
    def is_daemon(self):
        return any(ref.get("kind") == "DaemonSet" for ref in self.metadata.get("ownerReferences", []))

    @property
    def containers(self):
        """Return the containers in the pod, if any, else an empty list."""
        return self["spec"].get("containers", [])

    @property
    def main(self):
        """
        Return the main container in the pod, if any, defined as the first container with a name
        in MAIN_CONTAINERS.  If there are none of those, return the first one.
        """
        if not self.containers:
            return None
        main = fn.first(fn.filter(lambda c: c["name"] in MAIN_CONTAINERS, self.containers))
        return main or self.containers[0]

    def resources(self, tag):
        return sum(Resources.extract(c["resources"].get(tag)) for c in self.containers)


class JobHelper(ItemHelper):

    @property
    def status(self):
        status = self.obj.get("status", {})
        if len(status) == 0:
            return "Unknown"
        # Per
        # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1JobStatus.md
        # and https://kubernetes.io/docs/concepts/workloads/controllers/job/
        for c in status.get("conditions", []):
            if c["status"] == "True":
                if c["type"] == "Failed":
                    return c.get("reason") or "Failed"
                if c["type"] == "Suspended":
                    return "Suspended"
                if c["type"] == "Complete":
                    return "Complete"
            if c["type"] == "FailureTarget":
                return "Failed"
            if c["type"] == "SuccessCriteriaMet":
                return "Complete"
        if status.get("active", 0) > 0:
            return "Running"
        return "Unknown"
