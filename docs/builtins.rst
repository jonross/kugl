Built-in tables
---------------

A note about data types

- Timestamps are stored as integers, representing seconds since the Unix
  epoch. Timestamps and deltas can be converted back to strings like
  ``2021-01-01 12:34:56Z`` or ``5d``, ``4h30m`` using the ``to_utc`` and
  ``to_age`` functions, below.
- Memory is stored as bytes, and can be coverted back to a string like
  ``1Gi`` or ``3.4Mi`` using the ``to_size`` function, below
- CPU and GPU limits are stored as floats

pods
~~~~

Built from ``kubectl get pods``, one row per pod. Two calls are made to
``get pods``, one to get textual outut of the STATUS column, since this
is difficult to determine from the pod detail.

NOTE: some of the containers in a pod may have no limits expressed. If
all have no limits for e.g. CPU, ``cpu_req`` will be null; otherwise, to
sum container resources, a null value will be treated as zero.

+-----------------------------+---------+--------------------------------+
| Column                      | Type    | Description                    |
+=============================+=========+================================+
| name                        | TEXT    | Pod name, from                 |
|                             |         | ``metadata.name``              |
+-----------------------------+---------+--------------------------------+
| uid                         | TEXT    | Pod UID, from ``metadata.uid`` |
+-----------------------------+---------+--------------------------------+
| namespace                   | TEXT    | Pod namespace, from            |
|                             |         | ``metadata.namespace``         |
+-----------------------------+---------+--------------------------------+
| node_name                   | TEXT    | Node name, from                |
|                             |         | ``spec.nodeName``              |
+-----------------------------+---------+--------------------------------+
| phase                       | TEXT    | Pod phase, from                |
|                             |         | ``status.phase``               |
+-----------------------------+---------+--------------------------------+
| status                      | TEXT    | Pod status as reported by      |
|                             |         | ``kubectl get pods``           |
+-----------------------------+---------+--------------------------------+
| creation_ts                 | INTEGER | Pod creation timestamp, from   |
|                             |         | ``metadata.creationTimestamp`` |
+-----------------------------+---------+--------------------------------+
| deletion_ts                 | INTEGER | Pod deletion timestamp (or     |
|                             |         | null) from                     |
|                             |         | ``metadata.deletionTimestamp`` |
+-----------------------------+---------+--------------------------------+
| is_daemon                   | INTEGER | 1 if the pod is in a           |
|                             |         | DaemonSet, 0 otherwise         |
+-----------------------------+---------+--------------------------------+
| command                     | TEXT    | The concatenated command args  |
|                             |         | from what appears to be the    |
|                             |         | main container (look for       |
|                             |         | containers named ``main``,     |
|                             |         | ``app``, or ``notebook``) else |
|                             |         | from the first container       |
+-----------------------------+---------+--------------------------------+
| cpu_req, gpu_req, mem_req   | REAL    | Sum of CPU, GPU and memory     |
|                             |         | values from                    |
|                             |         | ``resources.requests`` in each |
|                             |         | ``spec.containers``; GPU looks |
|                             |         | for the value tagged           |
|                             |         | ``nvidia.com/gpu``             |
+-----------------------------+---------+--------------------------------+
| cpu_lim, gpu_lim, mem_lim   | REAL    | Sum of CPU, GPU and memory     |
|                             |         | values from                    |
|                             |         | ``resources.limits`` in each   |
|                             |         | ``spec.containers``; GPU looks |
|                             |         | for the value tagged           |
|                             |         | ``nvidia.com/gpu`` (this isn't |
|                             |         | necessarily helpful, since     |
|                             |         | limits can be absent)          |
+-----------------------------+---------+--------------------------------+

pod_labels
~~~~~~~~~~

Built from ``kubectl get pods``, one row per label.

+------------+------+--------------------------------------------------+
| Column     | Type | Description                                      |
+============+======+==================================================+
| pod_uid    | TEXT | Pod UID, from ``metadata.uid``                   |
+------------+------+--------------------------------------------------+
| key, value | TEXT | Label key and value from each entry in           |
|            |      | ``metadata.labels``                              |
+------------+------+--------------------------------------------------+

jobs
~~~~

Built from ``kubectl get jobs``, one row per job

+-------------------------------+------+----------------------------------------------------------------------------------------------------------+
| Column                        | Type | Description                                                                                              |
+===============================+======+==========================================================================================================+
| name                          | TEXT | Job name, from ``metadata.name``                                                                         |
+-------------------------------+------+----------------------------------------------------------------------------------------------------------+
| uid                           | TEXT | Job UID, from ``metadata.uid``                                                                           |
+-------------------------------+------+----------------------------------------------------------------------------------------------------------+
| namespace                     | TEXT | Job namespace, from ``metadata.namespace``                                                               |
+-------------------------------+------+----------------------------------------------------------------------------------------------------------+
| status                        | TEXT | Job status as described by                                                                               |
|                               |      | `V1JobStatus <https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1JobStatus.md>`__ |
|                               |      | -- this is one of ``Running``, ``Complete``, ``Suspended``, Failed\ ``,``\ Unknown\`                     |
+-------------------------------+------+----------------------------------------------------------------------------------------------------------+
| cpu_req, gpu_req, mem_req     | REAL | Sum of CPU, GPU and memory values from ``resources.requests`` in each ``spec.template.spec.containers``; |
|                               |      | GPU looks for the value tagged ``nvidia.com/gpu``                                                        |
+-------------------------------+------+----------------------------------------------------------------------------------------------------------+
| cpu_lim, gpu_lim, mem_lim     | REAL | Sum of CPU, GPU and memory values from ``resources.limits`` in each ``spec.template.spec.containers``;   |
|                               |      | GPU looks for the value tagged ``nvidia.com/gpu`` (this isn't necessarily helpful, since limits can be   |
+-------------------------------+------+----------------------------------------------------------------------------------------------------------+

job_labels
~~~~~~~~~~

Built from ``kubectl get jobs``, one row per label.

+------------+------+--------------------------------------------------+
| Column     | Type | Description                                      |
+============+======+==================================================+
| job_uid    | TEXT | Job UID, from ``metadata.uid``                   |
+------------+------+--------------------------------------------------+
| key, value | TEXT | Label key and value from each entry in           |
|            |      | ``metadata.labels``                              |
+------------+------+--------------------------------------------------+

cronjobs
~~~~~~~~

Built from ``kubectl get cronjobs``, one row per cronjob.

+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| Column                        | Type    | Description                                                                                              |
+===============================+=========+==========================================================================================================+
| name                          | TEXT    | CronJob name, from ``metadata.name``                                                                     |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| uid                           | TEXT    | CronJob UID, from ``metadata.uid``                                                                       |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| namespace                     | TEXT    | CronJob namespace, from ``metadata.namespace``                                                           |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| schedule                      | TEXT    | Cron schedule expression, from ``spec.schedule``                                                         |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| suspend                       | INTEGER | 1 if the cronjob is suspended, 0 otherwise                                                               |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| active                        | INTEGER | Number of currently active jobs, from ``status.active``                                                  |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| last_schedule_ts              | INTEGER | Last schedule time, from ``status.lastScheduleTime`` (or null)                                           |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| last_success_ts               | INTEGER | Last successful completion time, from ``status.lastSuccessfulTime`` (or null)                            |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| cpu_req, gpu_req, mem_req     | REAL    | Sum of CPU, GPU and memory values from ``resources.requests`` in each job template container;            |
|                               |         | GPU looks for the value tagged ``nvidia.com/gpu``                                                        |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+
| cpu_lim, gpu_lim, mem_lim     | REAL    | Sum of CPU, GPU and memory values from ``resources.limits`` in each job template container;              |
|                               |         | GPU looks for the value tagged ``nvidia.com/gpu`` (this isn't necessarily helpful, since limits can be   |
|                               |         | absent)                                                                                                  |
+-------------------------------+---------+----------------------------------------------------------------------------------------------------------+

cronjob_labels
~~~~~~~~~~~~~~

Built from ``kubectl get cronjobs``, one row per label.

+----------------+------+--------------------------------------------------+
| Column         | Type | Description                                      |
+================+======+==================================================+
| cronjob_uid    | TEXT | CronJob UID, from ``metadata.uid``               |
+----------------+------+--------------------------------------------------+
| key, value     | TEXT | Label key and value from each entry in           |
|                |      | ``metadata.labels``                              |
+----------------+------+--------------------------------------------------+

nodes
~~~~~

Built from ``kubectl get nodes``, one row per node. See `recommended
configuration <./recommended.rst>`__ about adding node instance type.

+-------------------------------+------+-------------------------------+
| Column                        | Type | Description                   |
+===============================+======+===============================+
| name                          | TEXT | Node name, from               |
|                               |      | ``metadata.name``             |
+-------------------------------+------+-------------------------------+
| uid                           | TEXT | Node UID, from                |
|                               |      | ``metadata.uid``              |
+-------------------------------+------+-------------------------------+
| cpu_alloc, gpu_alloc,         | REAL | CPU, GPU and memory values    |
| mem_alloc                     |      | from ``status.allocatable``;  |
|                               |      | GPU looks for the value       |
|                               |      | tagged ``nvidia.com/gpu``     |
+-------------------------------+------+-------------------------------+
| cpu_cap, gpu_cap, mem_cap     | REAL | CPU GPU and memory values     |
|                               |      | from ``status.capacity``; GPU |
|                               |      | looks for the value tagged    |
|                               |      | ``nvidia.com/gpu``            |
+-------------------------------+------+-------------------------------+

node_labels
~~~~~~~~~~~

Built from ``kubectl get nodes``, one row per label.

+------------+------+--------------------------------------------------+
| Column     | Type | Description                                      |
+============+======+==================================================+
| node_uid   | TEXT | Node UID, from ``metadata.uid``                  |
+------------+------+--------------------------------------------------+
| key, value | TEXT | Label key and value from each entry in           |
|            |      | ``metadata.labels``                              |
+------------+------+--------------------------------------------------+

node_taints
~~~~~~~~~~~

Built from ``kubectl get nodes``, one row per taint

+--------------------+------+------------------------------------------+
| Column             | Type | Description                              |
+====================+======+==========================================+
| node_uid           | TEXT | Node UID, from ``metadata.uid``          |
+--------------------+------+------------------------------------------+
| key, value, effect | TEXT | Taint key, value and effect from each    |
|                    |      | entry in ``spec.taints``                 |
+--------------------+------+------------------------------------------+

services
~~~~~~~~

Built from ``kubectl get services``, one row per service.

+-------------+---------+--------------------------------------------------+
| Column      | Type    | Description                                      |
+=============+=========+==================================================+
| name        | TEXT    | Service name, from ``metadata.name``             |
+-------------+---------+--------------------------------------------------+
| uid         | TEXT    | Service UID, from ``metadata.uid``               |
+-------------+---------+--------------------------------------------------+
| namespace   | TEXT    | Service namespace, from ``metadata.namespace``   |
+-------------+---------+--------------------------------------------------+
| type        | TEXT    | Service type: ``ClusterIP``, ``NodePort``,       |
|             |         | ``LoadBalancer``, or ``ExternalName``            |
+-------------+---------+--------------------------------------------------+
| cluster_ip  | TEXT    | Cluster IP, from ``spec.clusterIP``; null for    |
|             |         | headless services and ``ExternalName`` type      |
+-------------+---------+--------------------------------------------------+
| external_ip | TEXT    | External IP or hostname for ``LoadBalancer``     |
|             |         | services, from ``status.loadBalancer.ingress``;  |
|             |         | null otherwise                                   |
+-------------+---------+--------------------------------------------------+
| creation_ts | INTEGER | Creation timestamp in epoch seconds, from        |
|             |         | ``metadata.creationTimestamp``                   |
+-------------+---------+--------------------------------------------------+

service_labels
~~~~~~~~~~~~~~

Built from ``kubectl get services``, one row per label.

+--------------+------+--------------------------------------------------+
| Column       | Type | Description                                      |
+==============+======+==================================================+
| service_uid  | TEXT | Service UID, from ``metadata.uid``               |
+--------------+------+--------------------------------------------------+
| key, value   | TEXT | Label key and value from each entry in           |
|              |      | ``metadata.labels``                              |
+--------------+------+--------------------------------------------------+

deployments
~~~~~~~~~~~

Built from ``kubectl get deployments``, one row per deployment.

+-------------+---------+--------------------------------------------------+
| Column      | Type    | Description                                      |
+=============+=========+==================================================+
| name        | TEXT    | Deployment name, from ``metadata.name``          |
+-------------+---------+--------------------------------------------------+
| uid         | TEXT    | Deployment UID, from ``metadata.uid``            |
+-------------+---------+--------------------------------------------------+
| namespace   | TEXT    | Deployment namespace, from                       |
|             |         | ``metadata.namespace``                           |
+-------------+---------+--------------------------------------------------+
| replicas    | INTEGER | Desired replica count, from ``spec.replicas``    |
+-------------+---------+--------------------------------------------------+
| ready       | INTEGER | Ready replicas, from ``status.readyReplicas``    |
+-------------+---------+--------------------------------------------------+
| available   | INTEGER | Available replicas, from                         |
|             |         | ``status.availableReplicas``                     |
+-------------+---------+--------------------------------------------------+
| updated     | INTEGER | Updated replicas, from                           |
|             |         | ``status.updatedReplicas``                       |
+-------------+---------+--------------------------------------------------+
| strategy    | TEXT    | Rollout strategy, from ``spec.strategy.type``;   |
|             |         | ``RollingUpdate`` or ``Recreate``                |
+-------------+---------+--------------------------------------------------+
| creation_ts | INTEGER | Creation timestamp in epoch seconds, from        |
|             |         | ``metadata.creationTimestamp``                   |
+-------------+---------+--------------------------------------------------+

deployment_labels
~~~~~~~~~~~~~~~~~

Built from ``kubectl get deployments``, one row per label.

+----------------+------+--------------------------------------------------+
| Column         | Type | Description                                      |
+================+======+==================================================+
| deployment_uid | TEXT | Deployment UID, from ``metadata.uid``            |
+----------------+------+--------------------------------------------------+
| key, value     | TEXT | Label key and value from each entry in           |
|                |      | ``metadata.labels``                              |
+----------------+------+--------------------------------------------------+

events
~~~~~~

Built from ``kubectl get events``, one row per event. Kubernetes deduplicates
repeated events, so ``count`` reflects how many times an event occurred rather
than the number of rows. Note that ``type`` and ``count`` conflict with SQL
keywords / aggregate function names and must be backtick-quoted in queries,
e.g. ``SELECT \`type\`, \`count\` FROM events``.

+---------------+---------+------------------------------------------------------------+
| Column        | Type    | Description                                                |
+===============+=========+============================================================+
| namespace     | TEXT    | Event namespace, from ``metadata.namespace``               |
+---------------+---------+------------------------------------------------------------+
| type          | TEXT    | Event type: ``Normal`` or ``Warning``; backtick-quote      |
|               |         | in SQL                                                     |
+---------------+---------+------------------------------------------------------------+
| reason        | TEXT    | Short machine-readable reason, e.g. ``Scheduled``,         |
|               |         | ``OOMKilling``                                             |
+---------------+---------+------------------------------------------------------------+
| message       | TEXT    | Human-readable event description                           |
+---------------+---------+------------------------------------------------------------+
| count         | INTEGER | Number of times this event has occurred; backtick-quote    |
|               |         | in SQL                                                     |
+---------------+---------+------------------------------------------------------------+
| first_ts      | INTEGER | First occurrence timestamp in epoch seconds, from          |
|               |         | ``firstTimestamp``                                         |
+---------------+---------+------------------------------------------------------------+
| last_ts       | INTEGER | Last occurrence timestamp in epoch seconds, from           |
|               |         | ``lastTimestamp``                                          |
+---------------+---------+------------------------------------------------------------+
| obj_kind      | TEXT    | Involved object kind, from ``involvedObject.kind``,        |
|               |         | e.g. ``Pod``, ``Node``                                     |
+---------------+---------+------------------------------------------------------------+
| obj_name      | TEXT    | Involved object name, from ``involvedObject.name``;        |
|               |         | primary join key to other tables                           |
+---------------+---------+------------------------------------------------------------+
| obj_namespace | TEXT    | Involved object namespace, from                            |
|               |         | ``involvedObject.namespace``                               |
+---------------+---------+------------------------------------------------------------+
| source        | TEXT    | Generating component, from ``source.component``,           |
|               |         | e.g. ``kubelet``, ``default-scheduler``                    |
+---------------+---------+------------------------------------------------------------+

Built-in functions
------------------

``now()`` - returns the current time as an integer, in epoch seconds

``to_utc(timestamp)`` - convert epoch time to string form e.g.
``YYYY-MM-DDTHH:MM:SSZ``

``to_age(seconds)`` - convert seconds to a more readable age string as
seen in the ``AGE`` column of ``kubectl get pods``, e.g. ``5d``,
``4h30m``.

``to_size(bytes)`` - convert a byte count to a more readable string,
e.g. ``1Gi``, ``3.4Mi``
