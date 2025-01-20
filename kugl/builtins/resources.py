import json
import sys
from os.path import expandvars, expanduser
from pathlib import Path
from typing import Union, Optional

import yaml
from pydantic import model_validator

from kugl.api import resource, fail, run, Resource


class NonCacheableResource(Resource):

    @model_validator(mode="after")
    @classmethod
    def set_cacheable(cls, resource: "NonCacheableResource") -> "NonCacheableResource":
        if resource.cacheable is True:
            fail(f"resource '{resource.name}' cannot be cacheable: true")
        resource.cacheable = False
        return resource


@resource("data")
class DataResource(NonCacheableResource):
    """A resource whose data is provided directly in the configuration file."""
    data: dict

    def get_objects(self):
        return self.data


@resource("file")
class FileResource(NonCacheableResource):
    """A resource that reads a file from disk.

    These are non-cacheable because'm not sure it's appropriate to mirror the folder structure of file
    resources under ~/.kuglcache.  Maybe that's just paranoia. But if we change this, make sure stdin
    is never cachable."""
    file: str

    def get_objects(self):
        if self.file == "stdin":
            return _parse(sys.stdin.read())
        try:
            file = expandvars(expanduser(self.file))
            return _parse(Path(file).read_text())
        except OSError as e:
            fail(f"failed to read {self.file}", e)


@resource("exec")
class ExecResource(Resource):
    exec: Union[str, list[str]]
    cache_key: Optional[str] = None

    @model_validator(mode="after")
    @classmethod
    def set_cacheable(cls, resource: "ExecResource") -> "ExecResource":
        # To be cacheable, a shell resource must have a cache key that varies with the environment,
        # or cache entries will collide.
        if resource.cacheable is None:
            resource.cacheable = False
        elif resource.cacheable is True:
            if resource.cache_key is None:
                fail(f"exec resource '{resource.name}' must have a cache key")
            if expandvars(resource.cache_key) == resource.cache_key:
                fail(f"exec resource '{resource.name}' cache_key does not contain non-empty environment references")
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

