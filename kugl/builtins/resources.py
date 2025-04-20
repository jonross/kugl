import json
import re
import sys
from os.path import expandvars, expanduser
from pathlib import Path
from typing import Union, Optional

import yaml
from pydantic import model_validator

from kugl.api import resource, fail, run, Resource
from kugl.util import best_guess_parse, KPath, debugging


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
            return best_guess_parse(sys.stdin.read())
        try:
            file = expandvars(expanduser(self.file))
            return KPath(file).parse()
        except OSError as e:
            fail(f"failed to read {self.file} in resource {self.name}", e)


@resource("folder")
class FolderResource(NonCacheableResource):
    """A resource that reads selectively from a folder tree.

    These are non-cacheable for the same reason as FileResource."""
    folder: Union[str, Path]
    glob: str
    match: str

    @model_validator(mode="after")
    @classmethod
    def validate_folder(cls, resource: "FolderResource"):
        try:
            resource._pattern = re.compile(resource.match)
        except Exception as e:  # re.compile can raise anything
            fail(f"Invalid regex {resource.match} in resource {resource.name}")
        if isinstance(resource.folder, str):
            resource.folder = KPath(expandvars(expanduser(resource.folder)))
        if not resource.folder.exists():
            fail(f"Missing resource folder {resource.folder}")
        return resource

    def get_objects(self):
        folder = KPath(expandvars(expanduser(str(self.folder))))
        files = [p.relative_to(folder) for p in folder.glob(self.glob)]
        if not files:
            fail(f"Glob {self.glob} in {folder} produced no files")
        result = []
        debug = debugging("folder")
        if debug:
            debug(f"Reviewing files for {self.glob} in {folder}")
        for file in files:
            m = self._pattern.search(str(file))
            if m:
                if debug:
                    debug(f"Adding {file} with match {m.groupdict()}")
                result.append(dict(content=folder.joinpath(file).parse(), match=m.groupdict()))
            else:
                if debug:
                    debug(f"Skipping {file}, did not match regex")
        return result


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
        return best_guess_parse(out)

    def cache_path(self):
        assert self.cache_key is not None  # should be covered by validator
        return f"{expandvars(self.cache_key)}/{self.name}.exec.json"