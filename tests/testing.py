import json
import os
from pathlib import Path
from typing import Optional, Tuple, Union

import yaml


def kubectl_response(kind: str, output: Union[str, dict]):
    """
    Put a mock response for 'kubectl get {kind} ...' into the mock responses folder,
    to be found by an invocation of ./kubectl in a test.
    :param kind: e.g. "pods", "nodes, "jobs" etc
    :param output: A dict (will be JSON-serialized) or a string (will be trimmed)
    """
    if isinstance(output, dict):
        output = json.dumps(output)
    else:
        output = str(output).strip()
    folder = Path(os.getenv("KUGEL_MOCKDIR"))
    folder.mkdir(exist_ok=True)
    folder.joinpath(kind).write_text(output)


def make_pod(name: str,
             no_metadata: bool = False,
             name_at_root: bool = False,
             no_name: bool = False,
             cpu_req: int = 1,
             cpu_lim: int = 2,
             mem_req: str = "1M",
             mem_lim: str = "2M",
             gpu: int = 0,
             ):
    """
    Construct a Pod dict from a generic chunk of pod YAML that we can alter to simulate different
    responses from the K8S API.

    :param no_metadata: Pretend there is no metadata
    :param name_at_root: Put the object name at top level, not in the metadata
    :param no_name: Pretend there is no object name
    :param cpu_req: CPU requested
    :param cpu_lim: CPU limit
    :param mem_req: Memory requested
    :param mem_lim: Memory limit
    :param gpu: Number of GPUs requested / limit
    """
    obj = yaml.safe_load(_resource("sample_pod.yaml"))
    if name_at_root:
        obj["name"] = name
    elif not no_name:
        obj["metadata"]["name"] = name
    if no_metadata:
        del obj["metadata"]
    resources = {
        "requests": {"cpu": f"{cpu_req}", "memory": mem_req},
        "limits": {"cpu": f"{cpu_lim}", "memory": mem_lim},
    }
    if gpu:
        resources["requests"]["nvidia.com/gpu"] = f"{gpu}"
        resources["limits"]["nvidia.com/gpu"] = f"{gpu}"
    obj["spec"]["containers"][0]["resources"] = resources
    return obj


def make_job(name: str,
             active_count: Optional[int] = None,
             condition: Optional[Tuple[str, str, Optional[str]]] = None,
             ):
    """
    Construct a Job dict from a generic chunk of pod YAML that we can alter to simulate different
    responses from the K8S API.

    :param name: Job name
    :param active_count: If present, the number of active pods
    :param condition: If present, a condition tuple (type, status, reason)
    """
    obj = yaml.safe_load(_resource("sample_job.yaml"))
    obj["metadata"]["name"] = name
    obj["metadata"]["labels"]["job-name"] = name
    if active_count is not None:
        obj["status"]["active"] = active_count
    if condition is not None:
        obj["status"]["conditions"] = [{"type": condition[0], "status": condition[1], "reason": condition[2]}]
    return obj


def _resource(filename: str):
    return Path(__file__).parent.joinpath("resources", filename).read_text()