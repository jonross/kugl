import json
import sys
import os.path
from pathlib import Path
from typing import Union

import yaml

from kugl.api import resource, fail, run, Resource


@resource("file")
class FileResource(Resource):
    file: str

    def __init__(self, **kwargs):
        kwargs["cacheable"] = False
        super().__init__(**kwargs)

    def get_objects(self):
        if self.file == "stdin":
            return _parse(sys.stdin.read())
        try:
            file = os.path.expandvars(os.path.expanduser(self.file))
            return _parse(Path(file).read_text())
        except OSError as e:
            fail(f"Failed to read {self.file}", e)


@resource("shell")
class ShellResource(Resource):
    exec: Union[str, list[str]]

    def get_objects(self):
        _, out, _ = run(resource.exec)
        return _parse(out)

    def cache_path(self):
        return f"{self.name}.shell.json"


def _parse(text):
    if not text:
        return {}
    if text[0] in "{[":
        return json.loads(text)
    return yaml.safe_load(text)

