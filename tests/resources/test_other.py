"""
Non-source-specific resource tests -- errors & edge cases.
"""

import pytest

from kugl.util import KuglError, kugl_home
from ..testing import assert_query


def test_config_with_missing_resource(test_home):
    """Ensure correct error when an undefined resource is used."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
        create:
          - table: stuff
            resource: stuff
            columns: []
    """)
    with pytest.raises(KuglError, match="Errors in .*kubernetes.yaml:\nTable 'stuff' needs undefined resource 'stuff'"):
        assert_query("SELECT * FROM stuff", "")


def test_untypeable_resource(hr):
    """A resource we can't type should fail."""
    config = hr.config()
    # Replace the HR schema's "people" resource with an untypeable one.
    config["resources"][0] = dict(name="people")
    hr.save(config)
    with pytest.raises(KuglError, match="Errors in .*hr.yaml:\ncan't infer type of resource 'people'"):
        assert_query(hr.PEOPLE_QUERY, None)


def test_namespaced_resources_are_kubernetes_resources(hr, capsys):
    """A resource with a namespace: attribute is of type Kubernetes."""
    config = hr.config()
    # Replace the HR schema's "people" resource with one that will be inferred as Kubernetes
    config["resources"][0] = dict(name="people", namespaced="true")
    hr.save(config)
    # This will fail because there's no Kubernetes "people" resource, but that's OK.
    with pytest.raises(SystemExit):
        assert_query(hr.PEOPLE_QUERY, None)
    _, err = capsys.readouterr()
    assert "failed to run [kubectl get people" in err
