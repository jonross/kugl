"""
Tests for data cache timeout behavior.
"""
import re
from types import SimpleNamespace

from kugl.builtins.schemas.kubernetes import KubernetesResource
from kugl.impl.engine import DataCache, CHECK, NEVER_UPDATE, ALWAYS_UPDATE, ResourceRef
from kugl.util import Age, features_debugged
from ..testing import assert_by_line


def test_cache(test_home, capsys):
    cache = DataCache(test_home, Age("1m"))
    mock_schema = SimpleNamespace(name="kubernetes")

    pods = ResourceRef(mock_schema, KubernetesResource(name="pods", namespaced=True))
    jobs = ResourceRef(mock_schema, KubernetesResource(name="jobs", namespaced=True))
    nodes = ResourceRef(mock_schema, KubernetesResource(name="nodes", namespaced=False))
    events = ResourceRef(mock_schema, KubernetesResource(name="events", cacheable=False, namespaced=True))
    all_res = {pods, jobs, nodes, events}

    for r in all_res:
        r.resource.handle_cli_options(SimpleNamespace(namespace="foo", all_namespaces=False))

    pods_file = cache.cache_path(pods)
    jobs_file = cache.cache_path(jobs)
    nodes_file = cache.cache_path(nodes)
    events_file = cache.cache_path(events)

    # Note: don't write jobs data
    pods_file.write_text("{}")
    nodes_file.write_text("{}")
    events_file.write_text("{}")

    pods_file.set_age(Age("50s"))  # not expired
    nodes_file.set_age(Age("70s"))  # expired
    events_file.set_age(Age("50s"))  # not expired, but not cacheable

    with features_debugged("cache"):

        refresh, max_age = cache.advise_refresh(all_res, NEVER_UPDATE)
        assert refresh == {jobs, events}
        assert max_age == 70
        out, err = capsys.readouterr()
        assert_by_line(err, [
            re.compile(r"cache: missing cache file.*/kubernetes/nocontext/foo\.jobs\.json"),
            re.compile(r"cache: found cache file.*/kubernetes/nocontext/foo\.nodes\.json"),
            re.compile(r"cache: found cache file.*/kubernetes/nocontext/foo\.pods\.json"),
            "cache: requested [kubernetes.events kubernetes.jobs kubernetes.nodes kubernetes.pods]",
            "cache: cacheable [kubernetes.jobs kubernetes.nodes kubernetes.pods]",
            "cache: non-cacheable [kubernetes.events]",
            "cache: ages kubernetes.jobs=None kubernetes.nodes=70 kubernetes.pods=50",
            "cache: expired [kubernetes.nodes]",
            "cache: missing [kubernetes.jobs]",
            "cache: refreshable [kubernetes.events kubernetes.jobs]",
        ])

        refresh, max_age = cache.advise_refresh(all_res, CHECK)
        assert refresh == {jobs, nodes, events}
        assert max_age == 50
        out, err = capsys.readouterr()
        assert_by_line(err, [
            re.compile(r"cache: missing cache file.*/kubernetes/nocontext/foo\.jobs\.json"),
            re.compile(r"cache: found cache file.*/kubernetes/nocontext/foo\.nodes\.json"),
            re.compile(r"cache: found cache file.*/kubernetes/nocontext/foo\.pods\.json"),
            "cache: requested [kubernetes.events kubernetes.jobs kubernetes.nodes kubernetes.pods]",
            "cache: cacheable [kubernetes.jobs kubernetes.nodes kubernetes.pods]",
            "cache: non-cacheable [kubernetes.events]",
            "cache: ages kubernetes.jobs=None kubernetes.nodes=70 kubernetes.pods=50",
            "cache: expired [kubernetes.nodes]",
            "cache: missing [kubernetes.jobs]",
            "cache: refreshable [kubernetes.events kubernetes.jobs kubernetes.nodes]",
        ])

        refresh, max_age = cache.advise_refresh(all_res, ALWAYS_UPDATE)
        assert refresh == all_res
        assert max_age is None
        out, err = capsys.readouterr()
        assert err == ""