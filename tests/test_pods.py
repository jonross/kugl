
from kubeql.pods import PodHelper
from kubeql.testing import make_pod

def test_basics():
    pod = make_pod()


def test_missing_metadata():
    """Verify pod.label() does not fail if metadata is missing"""
    pod = make_pod(no_metadata=True)
    assert pod.label("foo") is None


def test_name():
    """Verify different locations for the pod name, including no name at all."""
    pod = make_pod()
    assert pod.name == "my-pod-xtsuotvlbalkdjrdjwawabvnm4zw7grhd2dy72m56u2crycyxwyq"
    pod = make_pod(name_at_root=True)
    assert pod.name == "my-pod-xtsuotvlbalkdjrdjwawabvnm4zw7grhd2dy72m56u2crycyxwyq"
    pod = make_pod(no_name=True)
    assert pod.name is None
