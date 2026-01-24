Note
----

Since configuration files can contain scripts, they should be protected
to the same degree as your shell scripts and anything on your
``PYTHONPATH.`` Kugl will refuse to read a configuration file that is
world-writable.

Exec resources
--------------

By replacing ``file: pathname`` with ``exec: some command`` you can have
Kugl run any shell script that generates JSON or YAML output. For
example, this is equivalent to the above ``file:`` resource:

.. code:: yaml

   resource:
     - name: kubeconfig
       exec: cat ~/.kube/config

Unlike file resources, the results of running external commands can be
cached, just as with Kubernetes resources. To enable this, set
``cacaheable: true`` and provide a ``cache_key`` that will be used to
generate the cache pathname. This will need to have at least one
environment variable reference, on the assumption that the command
output can vary based on the environment.

For an example, see the table built on ``aws ec2``
`here <./multi.rst>`__.

File resources
--------------

Kugl can be used to query YAML data in a file. For instance, this will
implement a bit of ``kubectl config get-contexts``.

.. code:: yaml

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

Then

.. code:: shell

   kugl "select name, cluster from contexts"

(Not that helpful, but you may have much larger config files worth
summarizing this way.)

Environment variable references like ``$HOME`` are allowed in resource
filenames. Using ``file: stdin`` also works, and lets you pipe JSON or
YAML to a Kugl query.

Folder resources
----------------

These are like ``file`` resources except they can match files in a tree.
Let's say you have a set of configuration files per AWS region, with
settings to be summarized from one specific file, example:

.. code:: shell

   ~/env/us-east-1/config.yaml
   ~/env/us-east-2/config.yaml
   ~/env/us-west-1/config.yaml
   ...

Within each config file is a set of environment variables:

.. code:: shell

   env:
     - name: AWS_REGION
       value: us-east-1
     - name: AWS_ACCOUNT
       value: 123456789012
     - name: AWS_VPC
       value: vpc-12345678

This folder resource definition will address each of the files.

.. code:: yaml

   resource:
     - name: by_region
       # The root of the folder tree
       folder: ~/env
       # Pattern to match files, as understood by Path.glob
       glob: "**/config.yaml"
       # Regexp to extract additional metadata from filenames
       match: "env/(?P<region>.+)/config.yaml"

The resource presents each file as a dictionary, with the ``match``
element offering the metadate extracted from the pattern match, example

.. code:: json

   [
       { "match":  {"region": "us-east-1" }, "content": { ... file contents ... } },
       { "match":  {"region": "us-east-2" }, "content": { ... file contents ... } },
       { "match":  {"region": "us-west-1" }, "content": { ... file contents ... } },
   ]

To build a table showing environment settings by region:

.. code:: yaml

   create:
     - table: env_settings
       resource: by_region
       row_source:
         # Address each element in the result list
         - "[]"
         # Focus on the environment settings
         - content.env
       columns:
         - name: region
           path: ^match.region
         - name: name
           path: name
         - name: value
           path: value
