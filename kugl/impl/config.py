"""
Pydantic models for configuration files.
"""

from os.path import expandvars, expanduser
from typing import Optional, Tuple, Callable, Union

import jmespath
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.functional_validators import model_validator

from .extract import ColumnType, KUGL_TYPE_TO_SQL_TYPE, LabelExtractor, PathExtractor
from kugl.util import Age, ConfigPath, parse_age, fail, abbreviate, warn, kugl_home, KPath, friendlier_errors

DEFAULT_SCHEMA = "kubernetes"

class ConfigContent(BaseModel):
    """Base class for the top-level classes of configuration files; this just tracks the source file."""
    _source: ConfigPath  # set by parse_file()


class Settings(BaseModel):
    """Holds the settings: entry from a user config file."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    cache_timeout: Union[Age, int] = Age(120)
    reckless: bool = False
    no_headers: bool = False
    init_path: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def preconvert_timeout(cls, model: dict) -> dict:
        # Pydantic doesn't handle Age objects in the config file, so we convert them to seconds here.
        if "cache_timeout" in model and isinstance(model["cache_timeout"], str):
            model["cache_timeout"] = parse_age(model["cache_timeout"])
        return model

    @model_validator(mode="after")
    @classmethod
    def validate_init_path(cls, settings: 'Settings') -> 'Settings':
        home_resolved = kugl_home().resolve()
        if any(KPath(x).resolve() == home_resolved for x in settings.init_path):
            fail("~/.kugl should not be listed in init_path")
        settings.init_path = [expandvars(expanduser(x)) for x in settings.init_path]
        return settings

    @model_validator(mode="after")
    @classmethod
    def convert_timeout(cls, settings: 'Settings') -> 'Settings':
        # If timeout specified in config, convert back to Age
        if isinstance(settings.cache_timeout, int):
            settings.cache_timeout = Age(settings.cache_timeout)
        return settings


class Shortcut(BaseModel):
    """Holds one entry from the shortcuts: section of a user config file."""
    model_config = ConfigDict(extra="forbid")
    name: str
    args: list[str]
    comment: Optional[str] = None


class SecondaryUserInit(ConfigContent):
    """The root model for init.yaml in folders other than kugl_home()"""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    shortcuts: list[Shortcut] = []

    @model_validator(mode="before")
    @classmethod
    def _rewrite_shortcuts(cls, model: dict) -> dict:
        """Handle the old form of shortcuts, which is just a dict of lists."""
        shortcuts = model.get("shortcuts")
        if isinstance(shortcuts, dict):
            warn("Shortcuts format has changed, please see https://github.com/jonross/kugl/blob/main/docs-tmp/shortcuts.md")
            model["shortcuts"] = [Shortcut(name=name, args=args) for name, args in shortcuts.items()]
        return model


class UserInit(SecondaryUserInit):
    """The root model for init.yaml; holds the entire file content."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    settings: Optional[Settings] = Settings()


class Column(BaseModel):
    """The minimal field set for a table column defined from code.  Columns defined from user
    config files use UserColumn, a subclass."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    name: str
    type: ColumnType = "text"
    comment: Optional[str] = None
    # SQL type for this column
    _sqltype: str

    @model_validator(mode="after")
    @classmethod
    def recognize_type(cls, column: 'Column') -> 'Column':
        column._sqltype = KUGL_TYPE_TO_SQL_TYPE[column.type]
        return column


class UserColumn(Column):
    """Holds one entry from a columns: list in a user config file."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    path: Optional[str] = None
    label: Optional[Union[str, list[str]]] = None
    # Parsed value of self.path
    _finder: jmespath.parser.Parser
    # Number of ^ in self.path
    _parents: int
    # Function to extract a column value from an object.
    _extract: Callable[[object], object]
    # Function to convert the extracted value to the SQL type
    _convert: type

    @model_validator(mode="after")
    @classmethod
    def gen_extractor(cls, column: 'UserColumn') -> 'UserColumn':
        """
        Generate the Extractor instance for a column definition; given an object, it will return
        a column value of the appropriate type.
        """
        if column.path and column.label:
            raise ValueError("cannot specify both path and label")
        elif column.path:
            column._extractor = PathExtractor(column.name, column.type, column.path)
        elif column.label:
            if not isinstance(column.label, list):
                column.label = [column.label]
            column._extractor = LabelExtractor(column.name, column.type, column.label)
        else:
            raise ValueError("must specify either path or label")
        return column

    def extract(self, obj: object, context) -> object:
        return self._extractor(obj, context)


class ExtendTable(BaseModel):
    """Holds the extend: section from a user config file."""
    model_config = ConfigDict(extra="forbid")
    table: str
    columns: list[UserColumn] = []


class ResourceDef(BaseModel):
    """Holds one entry from the resources: list in a user config file.

    This only ensures the .name and .cacheable attributes are properly typed.  The remaining
    validation happens in registry.py when we create a (possibly) schema-specific Resource.
    """
    model_config = ConfigDict(extra="allow")
    name: str
    cacheable: Optional[bool] = None


class CreateTable(ExtendTable):
    """Holds the create: section from a user config file."""
    resource: str
    row_source: Optional[list[str]] = None


class UserConfig(ConfigContent):
    """The root model for a user config file; holds the complete file content."""
    model_config = ConfigDict(extra="forbid")
    resources: list[ResourceDef] = []
    extend: list[ExtendTable] = []
    create: list[CreateTable] = []
    # User can put chunks of reusable YAML under here, we will ignore
    utils: Optional[object] = None


# FIXME use typevars
def parse_model(model_class, root: dict, return_errors: bool = False) -> Union[object, Tuple[Optional[object], Optional[list[str]]]]:
    """Parse a dict into a model instance (typically a UserConfig).

    :param model_class: The Pydantic model class to use for validation.
    :param source: The dict to parse
    :param return_errors: If True, return a tuple of (result, errors) instead of failing on errors."""
    try:
        result = model_class.model_validate(root)
        return (result, None) if return_errors else result
    except ValidationError as e:
        errors = friendlier_errors(e.errors())
        if return_errors:
            return None, errors
        fail("\n".join(errors))


# FIXME use typevars
def parse_file(model_class, path: ConfigPath) -> object:
    """Parse a configuration file into a model instance, handling edge cases."""
    if not path.exists():
        result = model_class()
    else:
        if path.is_world_writeable():
            fail(f"{path} is world writeable, refusing to run")
        result = parse_model(model_class, path.parse() or {})
    if isinstance(result, ConfigContent):
        result._source = path
    return result
