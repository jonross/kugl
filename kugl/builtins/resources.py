import json
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel

from kugl.api import resource, fail


@resource("file")
class FileResource(BaseModel):
    file: str

    def get_objects(self):
        if self.file == "stdin":
            return _parse(sys.stdin.read())
        try:
            return _parse(Path(self.file).read_text())
        except OSError as e:
            fail(f"Failed to read {self.file}", e)


def _parse(text):
    if not text:
        return {}
    if text[0] in "{[":
        return json.loads(text)
    return yaml.safe_load(text)

