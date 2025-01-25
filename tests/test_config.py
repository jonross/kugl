"""
Tests for user configuration file content.
"""
import pytest

from kugl.impl.config import Settings, UserConfig, parse_model, ExtendTable, CreateTable, UserInit

import yaml

from kugl.main import main1
from kugl.util import Age, kugl_home, KuglError


def test_settings_defaults():
    s = Settings()
    assert s.cache_timeout == Age(120)
    assert s.reckless == False


def test_settings_custom():
    s = Settings(cache_timeout=Age(5), reckless=True)
    assert s.cache_timeout == Age(5)
    assert s.reckless == True


def test_empty_config():
    c = UserConfig()
    assert c.extend == []
    assert c.create == []


def test_empty_init():
    c = UserInit()
    assert c.settings.cache_timeout == Age(120)
    assert c.settings.reckless == False
    assert c.shortcuts == {}


def test_config_with_table_extension():
    c = parse_model(UserConfig, yaml.safe_load("""
        extend:
          - table: pods
            columns:
              - name: foo
                path: metadata.name
                comment: a comment
              - name: bar
                type: integer
                path: metadata.creationTimestamp
    """))
    columns = c.extend[0].columns
    assert columns[0].name == "foo"
    assert columns[0].type == "text"
    assert columns[0].path == "metadata.name"
    assert columns[0].comment == "a comment"
    assert columns[1].name == "bar"
    assert columns[1].type == "integer"
    assert columns[1].path == "metadata.creationTimestamp"
    assert columns[1].comment is None


def test_config_with_table_creation():
    c = parse_model(UserConfig, yaml.safe_load("""
        resources:
          - name: pods
        create:
          - table: pods
            resource: pods
            columns:
              - name: foo
                path: metadata.name
              - name: bar
                type: integer
                path: metadata.creationTimestamp
    """))
    pods = c.create[0]
    assert pods.resource == "pods"
    columns = pods.columns
    assert columns[0].name == "foo"
    assert columns[0].type == "text"
    assert columns[0].path == "metadata.name"
    assert columns[1].name == "bar"
    assert columns[1].type == "integer"
    assert columns[1].path == "metadata.creationTimestamp"


def test_unknown_type():
    errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
          - name: foo
            type: unknown_type
            path: metadata.name
    """), return_errors=True)
    assert len(errors) == 1
    assert "columns.0.type: Input should be" in errors[0]


def test_missing_fields_for_create():
    errors = parse_model(CreateTable, yaml.safe_load("""
        table: xyz
        columns:
          - name: foo
            path: metadata.name
    """), return_errors=True)
    assert set(errors) == set([
        "resource: Field required",
    ])


def test_unexpected_keys():
    errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
          - name: foo
            path: metadata.name
            unexpected: 42
    """), return_errors=True)
    assert errors == ["columns.0.unexpected: Extra inputs are not permitted"]


def test_invalid_jmespath():
    errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
          - name: foo
            path: ...name
    """), return_errors=True)
    assert errors == ["columns.0: Value error, invalid JMESPath expression ...name in column foo"]


def test_cannot_have_both_path_and_label():
    errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
          - name: foo
            type: text
            path: xyz
            label: xyz
    """), return_errors=True)
    assert errors == ["columns.0: Value error, cannot specify both path and label"]


def test_must_specify_path_or_label():
    errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
          - name: foo
    """), return_errors=True)
    assert errors == ["columns.0: Value error, must specify either path or label"]