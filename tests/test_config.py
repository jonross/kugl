import pytest
from pydantic import ValidationError

from kugel.config import Settings, Config, validate_config

import yaml

from kugel.helpers import Resources


def test_settings_defaults():
    s = Settings()
    assert s.cache_timeout == 120
    assert s.reckless == False


def test_settings_custom():
    s = Settings(cache_timeout=5, reckless=True)
    assert s.cache_timeout == 5
    assert s.reckless == True


def test_empty_config():
    c = Config()
    assert c.settings.cache_timeout == 120
    assert c.settings.reckless == False
    assert c.extend == {}
    assert c.create == {}
    assert c.alias == {}


def test_config_with_table_extension():
    c, _ = validate_config(yaml.safe_load("""
        extend:
          pods:
            columns:
              foo:
                type: str
                source: metadata.name
              bar:
                type: int
                source: metadata.creationTimestamp
    """))
    columns = c.extend["pods"].columns
    assert columns["foo"].type == "str"
    assert columns["foo"].source == "metadata.name"
    assert columns["bar"].type == "int"
    assert columns["bar"].source == "metadata.creationTimestamp"


def test_config_with_table_creation():
    c, _ = validate_config(yaml.safe_load("""
        create:
          pods:
            resource: pods
            namespaced: true
            columns:
              foo:
                type: str
                source: metadata.name
              bar:
                type: int
                source: metadata.creationTimestamp
    """))
    pods = c.create["pods"]
    assert pods.resource == "pods"
    assert pods.namespaced == True
    columns = pods.columns
    assert columns["foo"].type == "str"
    assert columns["foo"].source == "metadata.name"
    assert columns["bar"].type == "int"
    assert columns["bar"].source == "metadata.creationTimestamp"


def test_unknown_type():
    _, errors = validate_config(yaml.safe_load("""
        extend:
          pods:
            columns:
              foo:
                type: unknown_type
                source: metadata.name
    """))
    assert errors == ["extend.pods.columns.foo.type: Input should be 'str', 'int' or 'float'"]


def test_missing_fields_for_create():
    _, errors = validate_config(yaml.safe_load("""
        create:
          pods:
            columns:
              foo:
                source: metadata.name
    """))
    assert set(errors) == set([
        "create.pods.columns.foo.type: Field required",
        "create.pods.resource: Field required",
        "create.pods.namespaced: Field required",
    ])


def test_unexpected_keys():
    _, errors = validate_config(yaml.safe_load("""
        extend:
          pods:
            columns:
              foo:
                type: str
                source: metadata.name
                unexpected: 42
    """))
    assert errors == ["extend.pods.columns.foo.unexpected: Extra inputs are not permitted"]


def test_invalid_jmespath():
    _, errors = validate_config(yaml.safe_load("""
        extend:
          pods:
            columns:
              foo:
                type: str
                source: ...name
    """))
    assert errors == ["extend.pods.columns.foo: Value error, invalid JMESPath expression ...name"]
