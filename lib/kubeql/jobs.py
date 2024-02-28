
from .dbmodel import Table
from .utils import K8SObjectHelper, MyConfig


class JobsTable(Table):

    NAME = "jobs"
    RESOURCE_KIND = "jobs"
    SCHEMA = """
        name TEXT,
        namespace TEXT,
        status TEXT,
        partition TEXT,
        workflow_id TEXT
    """

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            job.name,
            job.namespace,
            job.status,
            job.label("jabba.pathai.com/partition-name"),
            job.label("jabba.pathai.com/workflow-id"),
        ) for job in map(JobHelper, kube_data)]


class JobHelper(K8SObjectHelper):

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