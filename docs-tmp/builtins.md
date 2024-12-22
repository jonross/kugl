
## Built-in tables

A note about data types

* Timestamps are stored as integers, representing seconds since the Unix epoch.  See below for conversion functions.

### pods

Built from `kubectl get pods`, one row per pod.  Two calls are made to `get pods`, one to get textual outut
of the STATUS column, since this is difficult to determine from the pod detail.

| Column                          | Type    | Description                                                                                                                                                     |
|---------------------------------|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name                            | TEXT    | Pod name, from `metadata.name`                                                                                                                                  |
| namespace                       | TEXT    | Pod namespace, from `metadata.namespace`                                                                                                                        |
| node_name                       | TEXT    | Node name, from `spec.nodeName`                                                                                                                                 |
| status                          | TEXT    | Pod status as reported by `kubectl get pods` (as text, not JSON)                                                                                                |
| creation_ts                     | INTEGER | Pod creation timestamp, from `metadata.creationTimestamp`                                                                                                       |
| is_daemon                    | INTEGER | 1 if the pod is in a DaemonSet, 0 otherwise                                                                                                                     |
| command                         | TEXT    | The concatenated command args from what appears to be the main container (look for containers named `main`, `app`, or `notebook`) else from the first container |
| cpu_req, gpu_req, mem_req       | REAL | Sum of CPU, GPU and memory values from `resources.requests` in each container; GPU looks for the value tagged `nvidia.com/gpu`                                  |
| cpu_lim, gpu_lim, mem_lim       | REAL | Sum of CPU, GPU and memory values from `resources.limits` in each container; GPU looks for the value tagged `nvidia.com/gpu`                                      |

### jobs

Built from `kubectl get jobs`, one row per job

| Column                          | Type    | Description                                                                                                                                                                                               |
|---------------------------------|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name                            | TEXT    | Job name, from `metadata.name`                                                                                                                                                                            |
| namespace                       | TEXT    | Job namespace, from `metadata.namespace`                                                                                                                                                                  |
| status                          | TEXT    | Job status as described by [V1JobStatus](https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1JobStatus.md) -- this is one of `Running`, `Complete`, `Suspended`, Failed`, `Unknown` |

### nodes

Built from `kubectl get nodes`, one row per node

| Column                          | Type    | Description                                                                                                 |
|---------------------------------|---------|-------------------------------------------------------------------------------------------------------------|
| name                            | TEXT    | Node name, from `metadata.name`                                                                             |
| instance_type                   | TEXT    | Node instance type, from the label `node.kubernetes.io/instance-type` or `beta.kubernetes.io/instance-type` |
| cpu_alloc, gpu_alloc, mem_alloc | REAL | CPU, GPU and memory values from `status.allocatable`; GPU looks for the value tagged `nvidia.com/gpu`       |
| cpu_cap, gpu_cap, mem_cap       | REAL | CPU GPU and memory values from `status.capacity`; GPU looks for the value tagged `nvidia.com/gpu`           |

### taints

Built from `kubectl get nodes`, one row per taint

| Column                          | Type    | Description                                                  |
|:--------------------------------|---------|--------------------------------------------------------------|
| node_name                       | TEXT    | Node name, from `metadata.name`                              |
| key, value, effect              | TEXT    | Taint key, value and effect from each entry in `spec.taints` |

## Built-in functions

`now()` - returns the current time as an integer, in epoch seconds

`to_utc(timestamp)` - convert epoch time to string form `YYYY-MM-DD HH:MM:SSZ`

`to_age(timestamp)` - convert epoch time to a human-readable age string as seen in the `AGE` column of `kubectl get pods`, e.g. `5d`, `4h30m`.
