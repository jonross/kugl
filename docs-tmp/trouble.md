
### Can I report a bug or recommend a feature?

Yes please, feel free to open an issue or pull request on Github.  
For bugs, please follow these guidelines and try to isolate the issue as best you can.

* Include the relevant configuration sections from your `init.yaml` and `kubernetes.yaml`
* Run the command that isn't working with `-D all` and include the entire output.  Use a low-activity namespace if possible,
so that the output is limited.  If there is too much output, you can post it to [pastebin.com](https://pastebin.com) or
a similar service and link to it.
* If the output includes secure information from your cluster, please redact it before posting.

### Can I give feedback without opening an issue?

Defintely.  You can reach the author at `kugel dot devel at gmail dot com`.

### I didn't receive a response to an issue or email

Like many open source committers, the author has a family and a day job.  🙂

Please be patient, and thank you for trying Kugel!

### I'm not seeing any output from my queries

Don't forget to use `-n/--namespace <namespace>` or `-a/--all-namespaces`.  The `default` namespace in
Kubernetes often has few or no resources.

### My custom table isn't working

Matching `row_source` and `path` to your data layout can be tricky.
* Build up one `row_source` at a time
* Extend parent references `"^"` and test `select * from` after each step
* Make sure JMESPath expressions for columns select single objects
* Don't try to debug `kubectl` and `kugel` at the same time; use the `stdin` resource and a static
JSON file for testing.