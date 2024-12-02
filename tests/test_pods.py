
from kugel.helpers import PodHelper

from .testing import make_pod


def test_missing_metadata():
    """Verify pod.label() does not fail if metadata is missing"""
    pod = PodHelper(make_pod("noname", no_metadata=True))
    assert pod.label("foo") is None


def test_name():
    """Verify different locations for the pod name, including no name at all."""
    pod = PodHelper(make_pod("mypod-1"))
    assert pod.name == "mypod-1"
    pod = PodHelper(make_pod("mypod-2", name_at_root=True))
    assert pod.name == "mypod-2"
    pod = PodHelper(make_pod("mypod-3", no_name=True))
    assert pod.name is None
