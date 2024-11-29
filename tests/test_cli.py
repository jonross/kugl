import pytest

from kubeql.main import main
from kubeql.utils import KubeQLError


def test_enforce_one_cache_option():
    with pytest.raises(KubeQLError, match="Cannot use both -c/--cache and -u/--update"):
        main("-c -u foo".split(" "))


def test_enforce_one_namespace_option():
    with pytest.raises(KubeQLError, match="Cannot use both -a/--all-namespaces and -n/--namespace"):
        main("-a -n x foo".split(" "))


def test_no_such_resource():
    with pytest.raises(KubeQLError, match="Not available for query"):
        main(["select * from foo"])