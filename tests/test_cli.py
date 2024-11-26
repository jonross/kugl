import pytest

from kubeql.main import main
from kubeql.utils import KubeQLError


def test_enforce_one_cache_option():
    with pytest.raises(KubeQLError, match="Cannot use both --cache and --update"):
        main("-c -u foo".split(" "))


def test_enforce_one_namespace_option():
    with pytest.raises(KubeQLError, match="Cannot use both --all-namespaces and --namespace"):
        main("-a -n x foo".split(" "))


def test_no_such_resource():
    with pytest.raises(KubeQLError, match="Not available for query"):
        main(["select * from foo"])