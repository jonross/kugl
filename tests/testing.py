import json
import os
from pathlib import Path
from typing import Optional, Tuple, Union

import yaml


def kubectl_response(kind: str, output: Union[str, dict]):
    """
    Put a mock response for 'kubectl get {kind} ...' into the mock responses folder,
    to be found by an invocation of ./kubectl in a test.
    :param kind: e.g. "pods", "nodes, "jobs" etc
    :param output: A dict (will be JSON-serialized) or a string (will be trimmed)
    """
    if isinstance(output, dict):
        output = json.dumps(output)
    else:
        output = str(output).strip()
    folder = Path(os.getenv("KUGEL_MOCKDIR"))
    folder.mkdir(exist_ok=True)
    folder.joinpath(kind).write_text(output)


def make_pod(name: str,
             no_metadata: bool = False,
             name_at_root: bool = False,
             no_name: bool = False,
             cpu_req: int = 1,
             cpu_lim: int = 2,
             mem_req: str = "1M",
             mem_lim: str = "2M",
             gpu: int = 0,
             ):
    """
    Construct a Pod dict from a generic chunk of pod YAML that we can alter to simulate different
    responses from the K8S API.

    :param no_metadata: Pretend there is no metadata
    :param name_at_root: Put the object name at top level, not in the metadata
    :param no_name: Pretend there is no object name
    :param cpu_req: CPU requested
    :param cpu_lim: CPU limit
    :param mem_req: Memory requested
    :param mem_lim: Memory limit
    :param gpu: Number of GPUs requested / limit
    """
    obj = yaml.safe_load(BASE_POD_YAML)
    if name_at_root:
        obj["name"] = name
    elif not no_name:
        obj["metadata"]["name"] = name
    if no_metadata:
        del obj["metadata"]
    resources = {
        "requests": {"cpu": f"{cpu_req}", "memory": mem_req},
        "limits": {"cpu": f"{cpu_lim}", "memory": mem_lim},
    }
    if gpu:
        resources["requests"]["nvidia.com/gpu"] = f"{gpu}"
        resources["limits"]["nvidia.com/gpu"] = f"{gpu}"
    obj["spec"]["containers"][0]["resources"] = resources
    return obj


BASE_POD_YAML = """
    apiVersion: v1
    kind: Pod
    metadata:
      annotations:
        example.com/abc: an annotation
        example.com/def: another annotation
      creationTimestamp: '2024-02-04T15:15:01Z'
      labels:
        example.com/uvw: a label
        example.com/xyz: another label
        job-name: my-important-job
      namespace: research
      ownerReferences:
      - apiVersion: batch/v1
        blockOwnerDeletion: true
        controller: true
        kind: Job
        name: my-important-job
        uid: f1452695-3268-49ac-8018-a3d91a1d0082
      resourceVersion: '2385628922'
      uid: 4e1ba9fe-2483-4881-88c8-a5b14b9998c1
    spec:
      containers:
      - command:
        - /bin/bash
        - -c
        - "echo 'Hello world'"
        env:
        - name: MY_JOB_NAME
          valueFrom:
            fieldRef:
              apiVersion: v1
              fieldPath: metadata.labels['job-name']
        - name: MY_POD_IP
          valueFrom:
            fieldRef:
              apiVersion: v1
              fieldPath: status.podIP
        - name: SOME_VAR
          value: SOME_VAL
        envFrom:
        - secretRef:
            name: super-secret-secret
            optional: true
        image: example.com/hello-world
        imagePullPolicy: Always
        name: main
        volumeMounts:
        - mountPath: /utils
          name: utils-volume
          readOnly: true
      dnsPolicy: ClusterFirst
      enableServiceLinks: true
      imagePullSecrets:
      - name: i-can-haz-images
      - name: i-can-haz-more-images
      nodeName: worker5
      preemptionPolicy: PreemptLowerPriority
      priority: 7500
      priorityClassName: important-stuff
      restartPolicy: Never
      schedulerName: my-scheduler
      securityContext: {}
      serviceAccount: default
      serviceAccountName: default
      terminationGracePeriodSeconds: 30
      tolerations:
      - key: example.com/research-node
        operator: Equal
        value: yes
      - effect: NoExecute
        key: node.kubernetes.io/not-ready
        operator: Exists
        tolerationSeconds: 300
      - effect: NoExecute
        key: node.kubernetes.io/unreachable
        operator: Exists
        tolerationSeconds: 300
      volumes:
      - hostPath:
          path: /opt/pod-utils
          type: Directory
        name: utils-volume
      - configMap:
          defaultMode: 420
          name: extra-utils
        name: extra-utils
      - emptyDir:
          medium: Memory
        name: dshm
      - downwardAPI:
          defaultMode: 420
          items:
          - fieldRef:
              apiVersion: v1
              fieldPath: metadata.labels
            path: labels
          - fieldRef:
              apiVersion: v1
              fieldPath: metadata.annotations
            path: annotations
        name: podinfo
    status:
      conditions:
      - lastProbeTime: null
        lastTransitionTime: '2024-02-04T15:15:01Z'
        status: 'True'
        type: Initialized
      - lastProbeTime: null
        lastTransitionTime: '2024-02-04T15:15:04Z'
        status: 'True'
        type: Ready
      - lastProbeTime: null
        lastTransitionTime: '2024-02-04T15:15:04Z'
        status: 'True'
        type: ContainersReady
      - lastProbeTime: null
        lastTransitionTime: '2024-02-04T15:15:01Z'
        status: 'True'
        type: PodScheduled
      containerStatuses:
      - containerID: docker://8627eb5f689cf5d0c9655a32e558066b0f2ddf566f2a93002b12a24f33b8cca0
        image: docker.example.com/example-com/hello-world:8eb819ada5834aabb188cd6889abe0f48dba80ed
        imageID: docker-pullable://docker.example.com/example-com/hello-world@sha256:cc6fc551890fd26d321b326eadf1c5dd249ea0034b6f0328f60593f245b9ed5b
        lastState: {}
        name: main
        ready: true
        restartCount: 0
        started: true
        state:
          running:
            startedAt: '2024-02-04T15:15:04Z'
      hostIP: 10.11.12.13
      phase: Running
      podIP: 10.200.201.202
      podIPs:
      - ip: 10.200.201.202
      qosClass: Burstable
      startTime: '2024-02-04T15:15:01Z'
"""


def make_job(name: str,
             active_count: Optional[int] = None,
             condition: Optional[Tuple[str, str, Optional[str]]] = None,
             ):
    """
    Construct a Job dict from a generic chunk of pod YAML that we can alter to simulate different
    responses from the K8S API.

    :param name: Job name
    :param active_count: If present, the number of active pods
    :param condition: If present, a condition tuple (type, status, reason)
    """
    obj = yaml.safe_load(BASE_JOB_YAML)
    obj["metadata"]["name"] = name
    obj["metadata"]["labels"]["job-name"] = name
    if active_count is not None:
        obj["status"]["active"] = active_count
    if condition is not None:
        obj["status"]["conditions"] = [{"type": condition[0], "status": condition[1], "reason": condition[2]}]
    return obj

BASE_JOB_YAML = """
    apiVersion: batch/v1
    kind: Job
    metadata:
      creationTimestamp: "2024-11-20T01:05:00Z"
      generation: 1
      labels:
        controller-uid: 60848f11-1ecb-4a20-b9aa-bc039cb98b88
        job-name: example-job-1
      name: example-job-1
      namespace: example
      resourceVersion: "3479929701"
      uid: 60848f11-1ecb-4a20-b9aa-bc039cb98b88
    spec:
      backoffLimit: 0
      completionMode: NonIndexed
      completions: 1
      parallelism: 1
      selector:
        matchLabels:
          controller-uid: 60848f11-1ecb-4a20-b9aa-bc039cb98b88
      suspend: false
      template:
        metadata:
          creationTimestamp: null
          labels:
            controller-uid: 60848f11-1ecb-4a20-b9aa-bc039cb98b88
            job-name: example-job-28867745
        spec:
          containers:
          - command:
            - echo
            - "Hello, world"
            image: alpine:latest
            name: example-job
            resources:
              requests:
                cpu: "1"
    status: {}
"""