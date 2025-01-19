import json
import sys
from os.path import expandvars, expanduser
from pathlib import Path
from typing import Union, Optional

import yaml
from pydantic import model_validator

from kugl.api import resource, fail, run, Resource


@resource("file")
class FileResource(Resource):
    file: str

    @model_validator(mode="after")
    @classmethod
    def set_cacheable(cls, resource: "FileResource") -> "FileResource":
        # File resources are not cacheable.  I'm not sure it's appropriate to mirror the folder
        # structure of file resources under ~/.kuglcache.  Maybe that's just paranoia.
        if resource.cacheable is True:
            fail(f"File resource {resource.name} cannot be cacheable")
        resource.cacheable = False
        return resource

    def get_objects(self):
        if self.file == "stdin":
            return _parse(sys.stdin.read())
        try:
            file = expandvars(expanduser(self.file))
            return _parse(Path(file).read_text())
        except OSError as e:
            fail(f"Failed to read {self.file}", e)


@resource("shell")
class ShellResource(Resource):
    exec: Union[str, list[str]]
    cache_key: Optional[str] = None

    @model_validator(mode="after")
    @classmethod
    def set_cacheable(cls, resource: "ShellResource") -> "ShellResource":
        # To be cacheable, a shell resource must have a cache key that varies with the environment,
        # or cache entries will collide.
        if resource.cacheable is None:
            resource.cacheable = False
        elif resource.cacheable is True:
            if resource.cache_key is None:
                fail(f"Exec resource {resource.name} must have a cache_key")
            if expandvars(resource.cache_key) == resource.cache_key:
                fail(f"Exec resource {resource.name} cache_key does not contain non-empty environment references")
        return resource

    def get_objects(self):
        _, out, _ = run(self.exec)
        return _parse(out)

    def cache_path(self):
        assert self.cache_key is not None  # should be covered by validator
        return f"{expandvars(self.cache_key)}/{self.name}.exec.json"


def _parse(text):
    if not text:
        return {}
    if text[0] in "{[":
        return json.loads(text)
    return yaml.safe_load(text)

