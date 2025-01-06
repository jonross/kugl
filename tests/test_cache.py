"""
Tests for data cache timeout behavior.
"""
import re
from types import SimpleNamespace

from kugl.builtins.schemas.kubernetes import KubernetesResource
from kugl.impl.engine import DataCache, CHECK, NEVER_UPDATE, ALWAYS_UPDATE
from kugl.util import Age, features_debugged
from tests.testing import assert_by_line


def test_cache(test_home, capsys):
    NS = "default"
    cache = DataCache(test_home, Age("1m"))

    pods = KubernetesResource(name="pods")
    jobs = KubernetesResource(name="jobs")
    nodes = KubernetesResource(name="nodes", namespaced=False)
    events = KubernetesResource(name="events", cacheable=False)
    all_res = {pods, jobs, nodes, events}

    for r in all_res:
        r.handle_cli_options(SimpleNamespace(namespace="foo", all_namespaces=False))

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
            re.compile(r"cache: missing cache file.*foo\.jobs\.json"),
            re.compile(r"cache: found cache file.*foo\.nodes\.json"),
            re.compile(r"cache: found cache file.*foo\.pods\.json"),
            "cache: requested [events jobs nodes pods]",
            "cache: cacheable [jobs nodes pods]",
            "cache: non-cacheable [events]",
            "cache: ages jobs=None nodes=70 pods=50",
            "cache: expired [nodes]",
            "cache: missing [jobs]",
            "cache: refreshable [events jobs]",
        ])

        refresh, max_age = cache.advise_refresh(all_res, CHECK)
        assert refresh == {jobs, nodes, events}
        assert max_age == 50
        out, err = capsys.readouterr()
        assert_by_line(err, [
            re.compile(r"cache: missing cache file.*foo\.jobs\.json"),
            re.compile(r"cache: found cache file.*foo\.nodes\.json"),
            re.compile(r"cache: found cache file.*foo\.pods\.json"),
            "cache: requested [events jobs nodes pods]",
            "cache: cacheable [jobs nodes pods]",
            "cache: non-cacheable [events]",
            "cache: ages jobs=None nodes=70 pods=50",
            "cache: expired [nodes]",
            "cache: missing [jobs]",
            "cache: refreshable [events jobs nodes]",
        ])

        refresh, max_age = cache.advise_refresh(all_res, ALWAYS_UPDATE)
        assert refresh == all_res
        assert max_age is None
        out, err = capsys.readouterr()
        assert err == ""