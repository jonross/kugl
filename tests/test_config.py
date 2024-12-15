"""
Tests for user configuration file content.
"""

from kugel.config import Settings, Config, parse_model, ColumnDef, ExtendTable, CreateTable

import yaml

from kugel.model import Age


def test_settings_defaults():
    s = Settings()
    assert s.cache_timeout == Age(120)
    assert s.reckless == False


def test_settings_custom():
    s = Settings(cache_timeout=Age(5), reckless=True)
    assert s.cache_timeout == Age(5)
    assert s.reckless == True


def test_empty_config():
    c = Config()
    assert c.settings.cache_timeout == Age(120)
    assert c.settings.reckless == False
    assert c.extend == {}
    assert c.create == {}
    assert c.alias == {}


def test_config_with_table_extension():
    c, e = parse_model(Config, yaml.safe_load("""
        extend:
          pods:
            columns:
              foo:
                type: str
                path: metadata.name
              bar:
                type: int
                path: metadata.creationTimestamp
    """))
    assert e is None
    columns = c.extend["pods"].columns
    assert columns["foo"].type == "str"
    assert columns["foo"].path == "metadata.name"
    assert columns["bar"].type == "int"
    assert columns["bar"].path == "metadata.creationTimestamp"


def test_config_with_table_creation():
    c, e = parse_model(Config, yaml.safe_load("""
        create:
          pods:
            resource: pods
            columns:
              foo:
                type: str
                path: metadata.name
              bar:
                type: int
                path: metadata.creationTimestamp
    """))
    assert e is None
    pods = c.create["pods"]
    assert pods.resource == "pods"
    columns = pods.columns
    assert columns["foo"].type == "str"
    assert columns["foo"].path == "metadata.name"
    assert columns["bar"].type == "int"
    assert columns["bar"].path == "metadata.creationTimestamp"


def test_unknown_type():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        columns:
          foo:
            type: unknown_type
            path: metadata.name
    """))
    assert errors == ["columns.foo.type: Input should be 'str', 'int' or 'float'"]


def test_missing_fields_for_create():
    _, errors = parse_model(CreateTable, yaml.safe_load("""
        columns:
          foo:
            path: metadata.name
    """))
    assert set(errors) == set([
        "resource: Field required",
    ])


def test_unexpected_keys():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        columns:
          foo:
            path: metadata.name
            unexpected: 42
    """))
    assert errors == ["columns.foo.unexpected: Extra inputs are not permitted"]


def test_invalid_jmespath():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        columns:
          foo:
            path: ...name
    """))
    assert errors == ["columns.foo: Value error, invalid JMESPath expression ...name"]


def test_cannot_have_both_path_and_label():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        columns:
          foo:
            type: str
            path: xyz
            label: xyz
    """))
    assert errors == ["columns.foo: Value error, cannot specify both path and label"]


def test_must_specify_path_or_label():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        columns:
          foo:
            type: str
    """))
    assert errors == ["columns.foo: Value error, must specify either path or label"]