"""
Unit tests for the --schema CLI option.
"""

import pytest

from kugl.main import main1
from kugl.util import KuglError
from ..testing import assert_by_line


def test_no_such_schema(test_home):
    with pytest.raises(KuglError, match="no configurations found for schema 'notfound'"):
        main1(["--schema", "notfound"])


def test_no_such_table(test_home):
    with pytest.raises(KuglError, match="Table 'blah' is not defined in schema kubernetes"):
        main1(["--schema", "kubernetes.blah"])


def test_print_one_table(test_home, capsys):
    main1(["--schema", "kubernetes.nodes"])
    out, err = capsys.readouterr()
    assert_by_line(out, """
        ## nodes
        name       text     node name, from metadata.name
        uid        text     node UID, from metadata.uid
        cpu_alloc  real     allocatable CPUs, from status.allocatable
        gpu_alloc  real     allocatable GPUs, or null if none
        mem_alloc  integer  allocatable memory, in bytes
        cpu_cap    real     CPU capacity, from status.capacity
        gpu_cap    real     GPU capacity, or null if none
        mem_cap    integer  memory capacity, in bytes
    """)


def test_print_entire_schema(test_home, capsys):
    main1(["--schema", "kubernetes"])
    out, err = capsys.readouterr()
    # Ensure all the table headers are present
    for table_name in ["jobs", "job_labels", "pods", "pod_labels", "node", "node_labels", "node_taints"]:
        assert f"## {table_name}" in out
    # Check a few specific lines
    assert "status     text     job status, one of 'Running', 'Complete', 'Suspended', 'Failed', 'Unknown'" in out
    assert "cpu_alloc  real     allocatable CPUs, from status.allocatable" in out
    assert "creation_ts  integer  creation timestamp in epoch seconds, from metadata.creationTimestamp" in out
    assert "effect    text  taint effect" in out