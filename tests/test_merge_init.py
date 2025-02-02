"""
Unit tests for multiple init.yaml on init_path.
"""

import pytest

from kugl.main import main1
from kugl.util import kugl_home, KuglError


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

