Shortcuts
---------

Saving queries
~~~~~~~~~~~~~~

The ``shortcuts`` section in ``~/.kugl/init.yaml`` is a map from query
names to lists of command-line arguments.

Example, to save the queries shown in the `README <../README.md>`__ and
in `recommended configuration <./recommended.rst>`__, add this to
``~/.kugl/init.yaml``:

.. code:: yaml

   shortcuts:
     
     - name: hi-mem
       args:
         - |
           SELECT name, to_size(mem_req) FROM pods 
           WHERE phase = 'Running'
           ORDER BY mem_req DESC LIMIT 15

     - name: nodes
       # Comment field is optional
       comment: Schedulable vs unschedulable capacity
       args:
         - |
           WITH t AS (
             SELECT node_uid, group_concat(key) AS taints FROM node_taints
             WHERE effect IN ('NoSchedule', 'NoExecute') GROUP BY 1
           )
           SELECT instance_type, count(1) AS count, sum(cpu_alloc) AS cpu, sum(gpu_alloc) AS gpu, t.taints
           FROM nodes LEFT OUTER JOIN t ON t.node_uid = nodes.uid
           GROUP BY 1, 5 ORDER BY 1, 5

To run, type ``kugl hi-mem`` or ``kugl nodes``.

Parameterized shortcuts
~~~~~~~~~~~~~~~~~~~~~~~

Shortcuts can declare named parameters, letting a single shortcut serve
multiple invocations with different values.

Declare parameter names in the ``params`` list and reference them in
``args`` as ``{{name}}`` tokens:

.. code:: yaml

   shortcuts:

     - name: pods-by-image
       args:
         - "SELECT pod_name, namespace FROM containers WHERE image LIKE '%{{img}}%'"
       params:
         - img

Supply values positionally on the command line:

.. code:: bash

   kugl pods-by-image nginx
   kugl -H pods-by-image nginx     # flags before the shortcut name still work

The number of positional arguments must match the number of declared
parameters exactly; a mismatch is an error.  Using a ``{{token}}`` in
``args`` without a matching entry in ``params`` is also an error, caught
at config-load time.
