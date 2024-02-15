import yaml

from .pods import PodHelper


def make_pod(no_metadata: bool = False,
             name_at_root: bool = False,
             no_name: bool = False,
             ):
    """
    Construct a PodHelper from a generic chunk of pod YAML that we can alter to simulate different
    responses from the K8S API.

    :param no_metadata: Pretend there is no metadata
    :param name_at_root: Put the object name at top level, not the metadata
    :param no_name: Pretend there is no object name
    """
    obj = yaml.safe_load(BASE_POD_YAML)
    if name_at_root:
        obj["name"] = obj["metadata"]["name"]
        del obj["metadata"]["name"]
    elif no_name:
        del obj["metadata"]["name"]
    if no_metadata:
        del obj["metadata"]
    return PodHelper(obj)


BASE_POD_YAML = """
    apiVersion: v1
    kind: Pod
    metadata:
      annotations:
        example.com/abc: an annotation
        example.com/def: another annotation
      creationTimestamp: '2024-02-04T15:15:01Z'
      generateName: my-pod-xtsuotvlbalkdjrdjwawabvnm4zw7grhd2dy72m56u2crycyxwyq
      labels:
        example.com/uvw: a label
        example.com/xyz: another label
        job-name: my-important-job
      name: my-pod-xtsuotvlbalkdjrdjwawabvnm4zw7grhd2dy72m56u2crycyxwyq
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
        resources:
          limits:
            cpu: 2
            memory: 2M
          requests:
            cpu: 1
            memory: 1M
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