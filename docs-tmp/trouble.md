
### My query isn't working

Don't forget to use `-n/--namespace <namespace>` or `-a/--all-namespaces`.  The `default` namespace in
Kubernetes often has few or no resources.

Read the [JMESPath tutorial](https://jmespath.org/tutorial.html) 
and [SQLite documentation](https://www.sqlite.org/docs.html) thoroughly.

Debug `row_source` and `path` problems by installing [jp](https://github.com/jmespath/jp) and feeding
it examples of your JSON data.  JMESPath and `jq` don't behave the same.

Several flags are available for the `--debug` option, try whatever seems relevant:
* `--debug cache` will print the cache files consulted and what resources will be refreshed
* `--debug fetch` will print each invocation of `kubectl`
* `--debug itemize` will print how many items are generated for each step in a `row_source`
* `--debug extract` will (verbosely) print the source and value of every row, by column
* `--debug sqlite` will show the SQL for all statements executed, including table creation

### I found a bug

Help me help you!  I don't have access to your Kubernetes cluster, so you'll have to capture the
neccessary detail.

* Follow recommendations for debugging queries, above.
* Use a low-activity namespace if possible, so the amount of data involved is small.
* Try to reproduce the problem with as simple a query as possible, ideally on one table with no joins.
* Run the command with the relevant `--debug` options and include the output
* If possible, include the content of the cache files that are named in the debug output.

If there is too much material, you can post it to a service like [Pastebin](https://pastebin.com).
If it includes secure information from your cluster, please redact it before posting.

### Can I give feedback without opening an issue?

Yes, for now please post to [this discussion](https://github.com/jonross/kugl/issues/106) on Github.

### I didn't receive a response

Like many open source committers, the author has a family and a day job.  🙂

Please be exceedingly patient, and thank you for trying Kugl!