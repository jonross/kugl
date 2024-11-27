import pytest
from pydantic import ValidationError

from kubeql.config import Settings, Config

import yaml


def test_settings_defaults():
    s = Settings()
    assert s.default_namespace == "default"
    assert s.cache_timeout == 120
    assert s.reckless == False


def test_settings_custom():
    s = Settings(default_namespace="foo", cache_timeout=5, reckless=True)
    assert s.default_namespace == "foo"
    assert s.cache_timeout == 5
    assert s.reckless == True


def test_empty_config():
    c = Config()
    assert c.settings.default_namespace == "default"
    assert c.settings.cache_timeout == 120
    assert c.settings.reckless == False
    assert c.extend == {}
    assert c.create == {}
    assert c.canned == {}


def test_config_with_table_extension():
    c = Config(**yaml.safe_load("""
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
    c = Config(**yaml.safe_load("""
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
    with pytest.raises(ValidationError, match="foo.type\n.*Input should be"):
        Config(**yaml.safe_load("""
            extend:
              pods:
                columns:
                  foo:
                    type: unknown_type
                    source: metadata.name
        """))


def test_missing_fields_for_create():
    with pytest.raises(ValidationError, match="Field required"):
        Config(**yaml.safe_load("""
            create:
              pods:
                columns:
                  foo:
                    source: metadata.name
        """))


def test_unexpected_keys():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Config(**yaml.safe_load("""
            extend:
              pods:
                columns:
                  foo:
                    type: str
                    source: metadata.name
                    unexpected: 42
        """))
