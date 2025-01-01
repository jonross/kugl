
### My query isn't working

Don't forget to use `-n/--namespace <namespace>` or `-a/--all-namespaces`.  The `default` namespace in
Kubernetes often has few or no resources.

Read the [JMESPath tutorial](https://jmespath.org/tutorial.html) 
and [SQLite documentation](https://www.sqlite.org/docs.html) thoroughly.

Debug `row_source` and `path` problems by installing [jp](https://github.com/jmespath/jp) and feeding
it examples of your JSON data.  JMESPath and `jq` don't behave the same.

Run `kugl` with `--debug itemize` to verify that there are rows available for column extraction.
Run with `--debug itemize,extract` to see each extracted column value and a portion of the data it came
from.

### I found a bug

Please be very sure.  I don't have access to your Kubernetes cluster, 
so reproducibility without `kubectl` may be essential.

Follow recommendations for debugging queries, above.
Use a low-activity namespace if possible, so that the output is limited.
Run the command that isn't working with `--debug all` and include the entire output.
If possible, include the content of the cache files that are named in the output.
If there is too much output, you can post it to a service like [Pastebin](https://pastebin.com).
If the output or cache content includes secure information from your cluster, please redact it before posting.

### Can I give feedback without opening an issue?

Yes, please post to [this discussion](https://github.com/jonross/kugl/issues/106) on Github.

### I didn't receive a response

Like many open source committers, the author has a family and a day job.  🙂

Please be patient, and thank you for trying Kugl!