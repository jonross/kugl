"""
Tests for data cache timeout behavior.
"""

from kugl.impl.config import ResourceDef
from kugl.impl.engine import DataCache, CHECK, NEVER_UPDATE, ALWAYS_UPDATE
from kugl.util import Age


def test_cache(test_home):
    NS = "default"
    cache = DataCache(test_home, Age("1m"))

    pods = ResourceDef(name="pods")
    jobs = ResourceDef(name="jobs")
    nodes = ResourceDef(name="nodes", namespaced=False)
    events = ResourceDef(name="events", cacheable=False)
    all = {pods, jobs, nodes, events}

    pods_file = cache.cache_path(NS, "pods")
    jobs_file = cache.cache_path(NS, "jobs")
    nodes_file = cache.cache_path(NS, "nodes")
    events_file = cache.cache_path(NS, "events")

    # Note: don't write jobs data
    pods_file.write_text("{}")
    nodes_file.write_text("{}")
    events_file.write_text("{}")

    pods_file.set_age(Age("50s"))  # not expired
    nodes_file.set_age(Age("70s"))  # expired
    events_file.set_age(Age("50s"))  # not expired, but not cacheable

    refresh, max_age = cache.advise_refresh(NS, all, NEVER_UPDATE)
    assert refresh == {jobs, events}
    assert max_age == 70

    refresh, max_age = cache.advise_refresh(NS, all, CHECK)
    assert refresh == {jobs, nodes, events}
    assert max_age == 50

    refresh, max_age = cache.advise_refresh(NS, all, ALWAYS_UPDATE)
    assert refresh == all
    assert max_age is None

