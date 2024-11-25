import pytest

from kubeql.main import main
from kubeql.utils import KubeQLError


def test_one_kind_of_update():
    with pytest.raises(KubeQLError, match="Cannot specify both --cache and --update"):
        main("-u -c foo".split(" "))


def test_no_such_resource():
    with pytest.raises(KubeQLError, match="Not available for query"):
        main(["select * from foo"])