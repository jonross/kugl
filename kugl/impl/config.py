"""
Pydantic models for configuration files.
"""

import re
from os.path import expandvars, expanduser
from typing import Optional, Tuple, Callable, Union

import jmespath
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.functional_validators import model_validator

from .extract import ColumnType, KUGL_TYPE_TO_SQL_TYPE, FieldRef, LabelExtractor, PathExtractor, is_label
from kugl.util import (
    Age,
    ConfigPath,
    parse_age,
    fail,
    warn,
    kugl_home,
    KPath,
    friendlier_errors,
)

DEFAULT_SCHEMA = "kubernetes"


class ConfigContent(BaseModel):
    """Base class for the top-level classes of configuration files; this just tracks the source file."""

    _source: ConfigPath  # set by parse_file()


class Settings(BaseModel):
    """Holds the settings: entry from a user config file."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    cache_timeout: Union[Age, int] = Age(120)
    quiet: bool = False
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
    def validate_init_path(cls, settings: "Settings") -> "Settings":
        home_resolved = kugl_home().resolve()
        if any(KPath(x).resolve() == home_resolved for x in settings.init_path):
            fail("~/.kugl should not be listed in init_path")
        settings.init_path = [expandvars(expanduser(x)) for x in settings.init_path]
        return settings

    @model_validator(mode="after")
    @classmethod
    def convert_timeout(cls, settings: "Settings") -> "Settings":
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
            warn(
                "Shortcuts format has changed, please see https://github.com/jonross/kugl/blob/main/docs-tmp/shortcuts.md"
            )
            model["shortcuts"] = [
                Shortcut(name=name, args=args) for name, args in shortcuts.items()
            ]
        return model


class UserInit(SecondaryUserInit):
    """The root model for init.yaml in kugl_home() - contains everything in SecondaryUserInit
    plus Settings."""

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
    def recognize_type(cls, column: "Column") -> "Column":
        column._sqltype = KUGL_TYPE_TO_SQL_TYPE[column.type]
        return column


class UserColumn(Column):
    """Holds one entry from a columns: list in a user config file."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True, populate_by_name=True)
    path: Optional[str] = None
    label: Optional[Union[str, list[str]]] = None
    from_: Optional[str] = Field(None, alias="from")
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
    def gen_extractor(cls, column: "UserColumn") -> "UserColumn":
        """
        Generate the Extractor instance for a column definition; given an object, it will return
        a column value of the appropriate type.
        """
        has_path = column.path is not None
        has_label = column.label is not None
        has_from = column.from_ is not None

        if has_from and (has_path or has_label):
            raise ValueError("cannot specify 'from' alongside 'path' or 'label'")
        if has_path and has_label:
            raise ValueError("cannot specify both path and label")

        if has_from:
            # Strip any 'in <name>' suffix; scope validation is deferred to rebuild_for_scope.
            target = re.sub(r"\s+in\s+[a-zA-Z_][a-zA-Z0-9_]*$", "", column.from_)
            if is_label(target):
                column._extractor = LabelExtractor(column.name, column.type, [target])
            else:
                column._extractor = PathExtractor(column.name, column.type, target)
        elif has_path:
            # Strip any 'in <name>' suffix before JMESPath compilation; scope resolution
            # is deferred to rebuild_for_scope when scope names are known.
            path_target = re.sub(r"\s+in\s+[a-zA-Z_][a-zA-Z0-9_]*$", "", column.path)
            column._extractor = PathExtractor(column.name, column.type, path_target)
        elif has_label:
            if not isinstance(column.label, list):
                column.label = [column.label]
            column._extractor = LabelExtractor(column.name, column.type, column.label)
        else:
            raise ValueError("must specify path, label, or from")
        return column

    def extract(self, obj: object, context) -> object:
        return self._extractor(obj, context)

    def rebuild_for_scope(self, scope_names: set, table_name: str):
        """Re-create the extractor with scope awareness for multi-step row_source tables.

        Called at TableFromConfig build time when scope names are known.
        """
        if self.path:
            ref = FieldRef.parse_scoped(self.path, scope_names)
            if ref.scope_name is None:
                fail(
                    f"Table '{table_name}', column '{self.name}': "
                    f"path '{self.path}' must end with 'in <name>' "
                    f"(one of: {sorted(scope_names)})"
                )
            try:
                self._extractor = PathExtractor(self.name, self.type, ref.target, scope_name=ref.scope_name)
            except ValueError as e:
                fail(str(e))
        elif self.label:
            labels = self.label if isinstance(self.label, list) else [self.label]
            scope_name = None
            stripped_labels = []
            for label in labels:
                ref = FieldRef.parse_scoped(label, scope_names)
                if ref.scope_name is None:
                    fail(
                        f"Table '{table_name}', column '{self.name}': "
                        f"label '{label}' must end with 'in <name>' "
                        f"(one of: {sorted(scope_names)})"
                    )
                if scope_name and scope_name != ref.scope_name:
                    fail(
                        f"Table '{table_name}', column '{self.name}': "
                        f"all labels must use the same scope name"
                    )
                scope_name = ref.scope_name
                stripped_labels.append(ref.target)
            self._extractor = LabelExtractor(self.name, self.type, stripped_labels, scope_name=scope_name)
        elif self.from_:
            ref = FieldRef.parse_scoped(self.from_, scope_names)
            if ref.scope_name is None:
                fail(
                    f"Table '{table_name}', column '{self.name}': "
                    f"'from' value '{self.from_}' must end with 'in <name>' "
                    f"(one of: {sorted(scope_names)})"
                )
            if is_label(ref.target):
                self._extractor = LabelExtractor(self.name, self.type, [ref.target], scope_name=ref.scope_name)
            else:
                try:
                    self._extractor = PathExtractor(self.name, self.type, ref.target, scope_name=ref.scope_name)
                except ValueError as e:
                    fail(str(e))


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
def parse_model(
    model_class, root: dict, return_errors: bool = False
) -> Union[object, Tuple[Optional[object], Optional[list[str]]]]:
    """Parse a dict into a model instance -- typically a UserConfig but applies anywhere we
    are parsing from user content, since it improves on some of Pydantic's error messages.

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
    """Parse a configuration file into a model instance.
    If the file doesn't exist, use the model's default constructor.
    Fail if the file is world-writeable (security risk.)"""
    if not path.exists():
        result = model_class()
    else:
        if path.is_world_writeable():
            fail(f"{path} is world writeable, refusing to run")
        result = parse_model(model_class, path.parse() or {})
    if isinstance(result, ConfigContent):
        result._source = path
    return result
