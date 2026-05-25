Troubleshooting
---------------

My query isn't working
~~~~~~~~~~~~~~~~~~~~~~

Don't forget to use ``-n/--namespace <namespace>`` or ``-A/--all-namespaces``. The
``default`` namespace in Kubernetes often has few or no resources.

Read the `JMESPath tutorial <https://jmespath.org/tutorial.html>`__ and
`SQLite documentation <https://www.sqlite.org/docs.html>`__ thoroughly.

Debug ``row_source`` and ``path`` problems by installing
`jp <https://github.com/jmespath/jp>`__ and feeding it examples of your
JSON data. JMESPath and ``jq`` don't behave the same.

Several flags are available for the ``--debug`` option, try whatever
seems relevant:

- ``--debug cache`` prints the cache files consulted and what resources
  will be refreshed
- ``--debug fetch`` prints each invocation of ``kubectl``
- ``--debug folder`` prints each file considered for a ``folder``
  resource
- ``--debug itemize`` summarizes the item generated for each step in a
  ``row_source`` (verbose)
- ``--debug extract`` prints the source and value of every row, by
  column (verbose)
- ``--debug sqlite`` shows the SQL for all statements executed,
  including table creation

These can be combined, e.g. ``--debug fetch,itemize``. To turn on all
debugging options, use ``--debug all``.

If all else fails, try Claude Code.  Tell it where to find the documentation
(or the code, if you have cloned the repository), and ask it to help you debug the problem.

I found a bug
~~~~~~~~~~~~~

Feel free to open an issue on Github.  Since I don't have access to your 
Kubernetes cluster, capture the necessary detail in your issue.

- Follow recommendations for debugging queries, above.
- Use a low-activity namespace if possible, so the amount of data
  involved is small.
- Try to reproduce the problem with as simple a query as possible,
  ideally on one table with no joins.
- Run the command with the relevant ``--debug`` options and include the
  output
- If possible, include the content of the cache files that are named in
  the debug output.

If there is too much material, you can post it to a service like
`Pastebin <https://pastebin.com>`__. If it includes secure information
from your cluster, please redact it before posting.

I have a question or idea
~~~~~~~~~~~~~~~~~~~~~~~~~

Please use Kugl's [discussions page](https://github.com/jonross/kugl/discussions) on Github.
(You'll need a Github account to post, but it's free.)

I didn't receive a response right away
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Like many open source committers, the author has a family and a day job.
🙂

Please be patient, and thank you for trying Kugl!
