.. warning::
   Configuration files should be protected to the same degree as your shell
   scripts and anything on your ``PYTHONPATH.`` Kugl will refuse to read a
   configuration file that is world-writable.

Recommended configuration
-------------------------

Instance type is a useful column to have in the ``nodes`` table.
Unfortunately, there is no standard label for it. You can fix this with
configuration. In ``~/.kugl/kubernetes.yaml``, add

.. code:: yaml

   extend:
     - table: nodes
       columns:
         - name: instance_type
           label:
             - node.kubernetes.io/instance-type
             - beta.kubernetes.io/instance-type

This will handle common cases. If your cluster uses a different label,
add it to the list. You can use Kugl itself to find what's available,
for example:

.. code:: shell

   kugl "select distinct key from node_labels where key like '%instance-type%'"

Once you've set up the correct labels, here's a handy report that
reports available capacity, partitioning nodes by instance type and
``NoSchedule`` / ``NoExecute`` taints:

.. code:: shell

   kugl "
       WITH t AS (
           SELECT node_uid, group_concat(key) AS taints FROM node_taints
           WHERE effect IN ('NoSchedule', 'NoExecute') GROUP BY 1
       )
       SELECT instance_type, count(1) AS count, sum(cpu_alloc) AS cpu, sum(gpu_alloc) AS gpu, t.taints
       FROM nodes LEFT OUTER JOIN t ON t.node_uid = nodes.uid
       GROUP BY 1, 5 ORDER BY 1, 5
   "

If this query is helpful, `save it <./shortcuts.rst>`__ for future use.
