"""
Wrappers to make JSON returned by kubectl easier to work with.
"""

from dataclasses import dataclass

import funcy as fn

from .constants import MAIN_CONTAINERS
from .jross import from_footprint


@dataclass
class Resources:
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


class JobHelper(ItemHelper):

    @property
    def status(self):
        status = self.obj.get("status", {})
        if len(status) == 0:
            return "Unknown"
        if status.get("active", 0) > 0:
            return "Running"
        completions = self.obj.get("spec", {}).get("completions", 1)
        if status.get("succeeded", 0) == completions:
            return "Succeeded"
        if status.get("failed", 0) == completions:
            return "Failed"
        conditions = status.get("conditions")
        if conditions is not None:
            current = [c for c in conditions if c["status"] == "True"]
            if len(current) > 0:
                return current[-1]["type"]
        return "TBD"
