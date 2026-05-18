"""
Unit tests for multiple init.yaml on init_path.
"""

import pytest

from kugl.main import main1
from kugl.util import kugl_home, KuglError
from ..testing import augment_file


def test_reject_kugl_home_in_init_path(test_home):
    """Ensure ~/.kugl/init.yaml does not contain ~/.kugl"""
    kugl_home().prep().joinpath("init.yaml").write_text(f"""
        settings:
            init_path:
              - /tmp/somewhere
              - {kugl_home()}
    """)
    with pytest.raises(KuglError, match="~/.kugl should not be listed in init_path"):
        main1(["select 1"])


@pytest.mark.parametrize("use_old_syntax", [True, False])
def test_simple_shortcut(test_home, capsys, use_old_syntax):
    """
    Verify basic shortcut functionality.
    Verify it works with the old syntax and outputs a warning.
    """
    if use_old_syntax:
        # Shortcut syntax before version 0.5
        content = """
            shortcuts:
              foo: ["select 1, 2"]
        """
    else:
        # Shortcut syntax as of version 0.5
        content = """
            shortcuts:
              - name: foo
                args: ["select 1, 2"]
        """
    kugl_home().prep().joinpath("init.yaml").write_text(content)
    main1(["foo"])
    out, err = capsys.readouterr()
    assert out == "  1    2\n" * 2
    if use_old_syntax:
        assert "Shortcuts format has changed" in err
    else:
        assert "Shortcuts format has changed" not in err


@pytest.mark.parametrize(
    "params,values,sql_template,check",
    [
        (["val"], ["hello"], "select '{{val}}' as x", lambda out: "hello" in out),
        (
            ["a", "b"],
            ["foo", "bar"],
            "select '{{a}}' as a, '{{b}}' as b",
            lambda out: "foo" in out and "bar" in out,
        ),
    ],
)
def test_shortcut_with_params(test_home, capsys, params, values, sql_template, check):
    """Verify parameterized shortcuts substitute values correctly."""
    kugl_home().prep().joinpath("init.yaml").write_text(f"""
        shortcuts:
          - name: foo
            args: ["{sql_template}"]
            params: {params}
    """)
    main1(["foo"] + values)
    out, _ = capsys.readouterr()
    assert check(out)


def test_shortcut_too_few_args(test_home):
    """Verify error when too few positional args are passed."""
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          - name: foo
            args: ["select '{{a}}' as a, '{{b}}' as b"]
            params: [a, b]
    """)
    with pytest.raises(KuglError, match="requires 2 argument\\(s\\): a, b"):
        main1(["foo", "only-one"])


def test_shortcut_too_many_args(test_home):
    """Verify error when extras are passed to a no-param shortcut."""
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          - name: foo
            args: ["select 1"]
    """)
    with pytest.raises(KuglError, match="takes no arguments"):
        main1(["foo", "extra"])


def test_shortcut_undeclared_param(test_home):
    """Verify error at config parse time for undeclared {{token}} in args."""
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          - name: foo
            args: ["select '{{undeclared}}'"]
            params: []
    """)
    with pytest.raises(KuglError, match="undeclared parameter"):
        main1(["foo"])


def test_shortcut_with_params_and_flag(test_home, capsys):
    """Verify flags like -H work alongside parameterized shortcuts."""
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          - name: foo
            args: ["select '{{val}}' as x"]
            params: [val]
    """)
    main1(["-H", "foo", "hello"])
    out, _ = capsys.readouterr()
    assert "hello" in out
    assert "x" not in out  # header suppressed


@pytest.mark.parametrize("dupe", [True, False])
def test_shortcuts_in_different_files(test_home, extra_home, dupe: bool, capsys):
    primary_init = kugl_home().joinpath("init.yaml")
    extra_init = extra_home.joinpath("init.yaml")
    with augment_file(primary_init) as data:
        data["shortcuts"] = [dict(name="foo", args=["select 1, 2"])]
    with augment_file(extra_init) as data:
        data["shortcuts"] = [dict(name="foo" if dupe else "bar", args=["select 1, 2"])]
    if dupe:
        with pytest.raises(KuglError, match="Duplicate shortcut 'foo'"):
            main1(["foo"])
    else:
        main1(["foo"])
        main1(["bar"])
        out, err = capsys.readouterr()
        assert out == "  1    2\n" * 4
