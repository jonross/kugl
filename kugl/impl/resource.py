import json
import os
import sys
from abc import abstractmethod
from argparse import ArgumentParser
from pathlib import Path
from threading import Thread

import yaml
from pydantic import BaseModel

from kugl.util import fail, WHITESPACE, run


class Resource(BaseModel):

    @abstractmethod
    def add_cli_options(self, ap: ArgumentParser):
        pass  # not required of subclasses

    @abstractmethod
    def handle_cli_options(self, args):
        pass  # not required of subclasses

    @abstractmethod
    def get_objects(self):
        raise NotImplementedError()


class FileResource(Resource):
    file: str

    def get_objects(self):
        if self.file == "stdin":
            return _parse(sys.stdin.read())
        try:
            return _parse(Path(self.file).read_text())
        except OSError as e:
            fail(f"Failed to read {self.file}", e)


class KubernetesResource(Resource):
    name: str
    namespaced: bool = True

    def add_cli_options(self, ap: ArgumentParser):
        ap.add_argument("-a", "--all-namespaces", default=False, action="store_true")
        ap.add_argument("-n", "--namespace", type=str)

    def handle_cli_options(self, args):
        if args.all_namespaces and args.namespace:
            fail("Cannot use both -a/--all-namespaces and -n/--namespace")
        if args.all_namespaces:
            # FIXME: engine.py and testing.py still use this
            self.ns = "__all"
            self.all_ns = True
        else:
            self.ns = args.namespace or "default"
            self.all_ns = False

    def get_objects(self) -> dict:
        """Fetch resources from Kubernetes using kubectl.

        :return: JSON as output by "kubectl get {self.name} -o json"
        """
        unit_testing = "KUGL_UNIT_TESTING" in os.environ
        namespace_flag = ["--all-namespaces"] if self.all_ns else ["-n", self.ns]
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
        if self.name:
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
        rows = [WHITESPACE.split(line.strip()) for line in output.strip().split("\n")]
        if len(rows) < 2:
            return {}
        header, rows = rows[0], rows[1:]
        name_index = header.index("NAME")
        status_index = header.index("STATUS")
        # It would be nice if 'kubectl get pods' printed the UID, but it doesn't, so use
        # "namespace/name" as the key.  (Can't use a tuple since this has to be JSON-dumped.)
        if self.all_ns:
            namespace_index = header.index("NAMESPACE")
            return {f"{row[namespace_index]}/{row[name_index]}": row[status_index] for row in rows}
        else:
            return {f"{self.ns}/{row[name_index]}": row[status_index] for row in rows}


def _parse(text):
    if not text:
        return {}
    if text[0] in "{[":
        return json.loads(text)
    return yaml.safe_load(text)

