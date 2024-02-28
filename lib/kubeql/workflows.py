
from .dbmodel import Table
from .utils import MyConfig, K8SObjectHelper


class WorkflowsTable(Table):

    NAME = "workflows"
    RESOURCE_KIND = "workflows"
    SCHEMA = """
        name TEXT,
        namespace TEXT,
        partition TEXT,
        id TEXT,
        url TEXT,
        phase TEXT,
        env_name TEXT
    """

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            w.name,
            w.namespace,
            w.label("jabba.pathai.com/partition-name"),
            w.label("jabba.pathai.com/workflow-id"),
            f'http://app.mle.pathai.com/jabba/workflows/view/{w.label("jabba.pathai.com/workflow-id")}',
            w.label("workflows.argoproj.io/phase"),
            w.obj["spec"]["templates"][0]["metadata"]["labels"].get("mle.pathai.com/mle-env-name"),
        ) for w in map(WorkflowHelper, kube_data)]


class WorkflowHelper(K8SObjectHelper):
    pass

