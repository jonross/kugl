
## Built-in tables

A note about data types

* Timestamps are stored as integers, representing seconds since the Unix epoch.  Timestamps and deltas can be converted
back to strings like `2021-01-01 12:34:56Z` or `5d`, `4h30m` using the `to_utc` and `to_age` functions, below.
* Memory is stored as bytes, and can be coverted back to a string like `1Gi` or `3.4Mi` using the `to_size` function, below
* CPU and GPU limits are stored as floats

### pods

Built from `kubectl get pods`, one row per pod.  Two calls are made to `get pods`, one to get textual outut
of the STATUS column, since this is difficult to determine from the pod detail.

| Column                    | Type    | Description                                                                                                                                                                                       |
|---------------------------|---------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name                      | TEXT    | Pod name, from `metadata.name`                                                                                                                                                                    |
| uid                       | TEXT    | Pod UID, from `metadata.uid`                                                                                                                                                                      |
| namespace                 | TEXT    | Pod namespace, from `metadata.namespace`                                                                                                                                                          |
| node_name                 | TEXT    | Node name, from `spec.nodeName`                                                                                                                                                                   |
| phase                     | TEXT    | Pod phase, from `status.phase`                                                                                                                                                                    |
| status                    | TEXT    | Pod status as reported by `kubectl get pods`                                                                                                                                                      |
| creation_ts               | INTEGER | Pod creation timestamp, from `metadata.creationTimestamp`                                                                                                                                         |
| is_daemon                 | INTEGER | 1 if the pod is in a DaemonSet, 0 otherwise                                                                                                                                                       |
| command                   | TEXT    | The concatenated command args from what appears to be the main container (look for containers named `main`, `app`, or `notebook`) else from the first container                                   |
| cpu_req, gpu_req, mem_req | REAL | Sum of CPU, GPU and memory values from `resources.requests` in each `spec.containers`; GPU looks for the value tagged `nvidia.com/gpu`                                                            |
| cpu_lim, gpu_lim, mem_lim | REAL | Sum of CPU, GPU and memory values from `resources.limits` in each `spec.containers`; GPU looks for the value tagged `nvidia.com/gpu` (this isn't necessarily helpful, since limits can be absent) |

### pod_labels

Built from `kubectl get pods`, one row per label.

| Column     | Type    | Description                                              |
|------------|---------|----------------------------------------------------------|
| pod_uid    | TEXT    | Pod UID, from `metadata.uid`                             |
| key, value | TEXT    | Label key and value from each entry in `metadata.labels` |

### jobs

Built from `kubectl get jobs`, one row per job

| Column                          | Type    | Description                                                                                                                                                                                               |
|---------------------------------|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name                            | TEXT    | Job name, from `metadata.name`                                                                                                                                                                            |
| uid                             | TEXT    | Job UID, from `metadata.uid`                                                                                                                                                                              |
| namespace                       | TEXT    | Job namespace, from `metadata.namespace`                                                                                                                                                                  |
| status                          | TEXT    | Job status as described by [V1JobStatus](https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1JobStatus.md) -- this is one of `Running`, `Complete`, `Suspended`, Failed`, `Unknown` |
| cpu_req, gpu_req, mem_req       | REAL | Sum of CPU, GPU and memory values from `resources.requests` in each `spec.template.spec.containers`; GPU looks for the value tagged `nvidia.com/gpu`                                                      |
| cpu_lim, gpu_lim, mem_lim       | REAL | Sum of CPU, GPU and memory values from `resources.limits` in each `spec.template.spec.containers`; GPU looks for the value tagged `nvidia.com/gpu` (this isn't necessarily helpful, since limits can be    |

### job_labels

Built from `kubectl get jobs`, one row per label.

| Column     | Type    | Description                                              |
|------------|---------|----------------------------------------------------------|
| job_uid    | TEXT    | Job UID, from `metadata.uid`                             |
| key, value | TEXT    | Label key and value from each entry in `metadata.labels` |

### nodes

Built from `kubectl get nodes`, one row per node.  See [recommended configuration](./recommended.md)
about adding node instance type.

| Column                          | Type    | Description                                                                                                 |
|---------------------------------|---------|-------------------------------------------------------------------------------------------------------------|
| name                            | TEXT    | Node name, from `metadata.name`                                                                             |
| uid                             | TEXT    | Node UID, from `metadata.uid`                                                                               |
| cpu_alloc, gpu_alloc, mem_alloc | REAL | CPU, GPU and memory values from `status.allocatable`; GPU looks for the value tagged `nvidia.com/gpu`       |
| cpu_cap, gpu_cap, mem_cap       | REAL | CPU GPU and memory values from `status.capacity`; GPU looks for the value tagged `nvidia.com/gpu`           |

### node_labels

Built from `kubectl get nodes`, one row per label.

| Column     | Type    | Description                                              |
|------------|---------|----------------------------------------------------------|
| node_uid   | TEXT    | Node UID, from `metadata.uid`                            |
| key, value | TEXT    | Label key and value from each entry in `metadata.labels` |

### node_taints

Built from `kubectl get nodes`, one row per taint

| Column             | Type    | Description                                                  |
|:-------------------|---------|--------------------------------------------------------------|
| node_uid           | TEXT    | Node UID, from `metadata.uid`                                |
| key, value, effect | TEXT    | Taint key, value and effect from each entry in `spec.taints` |

## Built-in functions

`now()` - returns the current time as an integer, in epoch seconds

`to_utc(timestamp)` - convert epoch time to string form e.g. `YYYY-MM-DDTHH:MM:SSZ`

`to_age(seconds)` - convert seconds to a more readable age string as seen in the `AGE` column of `kubectl get pods`, e.g. `5d`, `4h30m`.

`to_size(bytes)` - convert a byte count to a more readable string, e.g. `1Gi`, `3.4Mi`