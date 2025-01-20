## File resources

Kugl can be used to query YAML data in a file.  For instance, this will implement a bit of `kubectl config get-contexts`.

```yaml
resource:
  - name: kubeconfig
    file: ~/.kube/config

create:
  - table: contexts
      resource: kubeconfig
      row_source:
        - contexts
      columns:
        - name: name
          path: name
        - name: cluster
          path: context.cluster
```

Then

```shell
kugl "select name, cluster from contexts"
```

(Not that helpful, but you may have much larger config files worth summarizing this way.)

Environment variable references like `$HOME` are allowed in resource filenames.
Using `file: stdin` also works, and lets you pipe JSON or YAML to a Kugl query.

## Exec resources

By replacing `file: pathname` with `exec: some command` you can have Kugl run any command line that generates
JSON or YAML output.  For example, this is equivalent to the above `file:` resource:

```yaml
resource:
  - name: kubeconfig
    exec: cat ~/.kube/config
```

Unlike file resources, the results of running external commands can be cached, just as with Kubernetes resources.
To enable this, set `cacaheable: true` and provide a `cache_key` that will be used to generate the cache pathname.
This will need to have at least one environment variable reference, on the assumption that the command output
can vary based on the environment.

For an example, see the table built on `aws ec2` [here](./multi.md).