"""
Wrappers to make JSON returned by kubectl easier to work with.
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional

import funcy as fn

from kugl.util import parse_size, parse_cpu

# What container name is considered the "main" container, if present
MAIN_CONTAINERS = ["main", "notebook", "app"]


@dataclass
class Limits:
    """
    A class to hold CPU, GPU and memory resources. This is called "Limits" although it's used for both requests
    and limits, so as not to confuse "resources" with Kubernetes resources in general.
    """
    cpu: Optional[float]
    gpu: Optional[float]
    mem: Optional[int]

    def __add__(self, other):
        if self.cpu is None and other.cpu is None:
            cpu = None
        else:
            cpu = (self.cpu or 0) + (other.cpu or 0)
        if self.gpu is None and other.gpu is None:
            gpu = None
        else:
            gpu = (self.gpu or 0) + (other.gpu or 0)
        if self.mem is None and other.mem is None:
            mem = None
        else:
            mem = (self.mem or 0) + (other.mem or 0)
        return Limits(cpu, gpu, mem)

    def __radd__(self, other):
        """Needed to support sum() -- handles 0 as a starting value"""
        return self if other == 0 else self.__add__(other)

    def as_tuple(self):
        return (self.cpu, self.gpu, self.mem)

    @classmethod
    def extract(cls, obj, debug=False):
        """Extract a Limits object from a dictionary, or return an empty one if the dictionary is None.

        :param obj: A dictionary with keys "cpu", "nvidia.com/gpu" and "memory" """
        if obj is None:
            if debug:
                print("No object provided to Limits extractor")
            return Limits(None, None, None)
        if debug:
            print("Extracting limits from", obj)
        cpu = parse_cpu(obj.get("cpu"))
        gpu = parse_cpu(obj.get("nvidia.com/gpu"))
        mem = parse_size(obj.get("memory"))
        result = Limits(cpu, gpu, mem)
        if debug:
            print("Extracted", result)
        return result


class ItemHelper:
    """Some common code for wrappers on JSON for pods, nodes et cetera."""

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
        """Return one of the labels from the object, or None if it doesn't have that label."""
        return self.labels.get(name)


class Containerized:

    @abstractmethod
    def containers(self):
        raise NotImplementedError()

    def resources(self, tag, debug=False):
        return sum(Limits.extract(c.get("resources", {}).get(tag), debug) for c in self.containers)


class PodHelper(ItemHelper, Containerized):

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
        """Return the main container in the pod, if any, defined as the first container with a name
        in MAIN_CONTAINERS.  If there are none of those, return the first one.
        """
        if not self.containers:
            return None
        main = fn.first(fn.filter(lambda c: c["name"] in MAIN_CONTAINERS, self.containers))
        return main or self.containers[0]


class JobHelper(ItemHelper, Containerized):

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
                    # TODO use a separate column
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

    @property
    def containers(self):
        """Return the containers in the job, if any, else an empty list."""
        return self["spec"]["template"]["spec"].get("containers", [])

