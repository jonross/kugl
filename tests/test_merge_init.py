"""
Unit tests for multiple init.yaml on init_path.
"""

import pytest

from kugl.main import main1
from kugl.util import kugl_home


@pytest.mark.parametrize("use_old_syntax", [True, False])
def test_simple_shortcut(test_home, capsys, use_old_syntax):
    if use_old_syntax:
        content = """
            shortcuts:
              foo: ["select 1, 2"]
        """
    else:
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

