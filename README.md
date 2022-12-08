
# masnet

`masnet` includes basic tools for Mastodon network/graph analysis.

`masnet.download` downloads the required data from Mastodon instances to create Mastodon network.

`masnet.generate` generates a network representation from the downloaded data.

# masnet.download

`masnet.download` connects to a given start domain (given with `-s` argument), downloads its peers (api/v1/instance/peers), and then repeats this for each peer until all domains are visited. 

After downloading the peers data of a domain, it is saved to a gzipped file (filename is domain with `.peers.json.gz` suffix). Thus, it is possible to restart the download safely. If needed, saved files can be discarded (with `-d`) and all of them are downloaded again.

In addition to caching the API response, `masnet.download` also saves the errors (to error files, file name domain with `.error` suffix) in order to not try to connect these after a restart. This behaviour is not controlled with `-d` argument, it is always enabled. If you want to retry these domains, delete the error files.

For network connections, a timeout can be specified with `-t` argument.

Because the download process is very I/O oriented, a number of Python threads are created to concurrently fetch peers data of different domains. The number of these threads can be specified with `-n` argument. Keep in mind Python is actually running in a single OS-thread, there is no multi-core processing here, Python threads are just time sharing the same core while waiting for I/O to finish.

Because there can be (many) malicious domains, it is possible to exclude them from traversal as they are seen in peers. Exclusion is specified as a string matching the domain name from the end, hence it is possible to filter all subdomains with a single string. For example, `.activitypub-troll.cf` would filter any domain ending with this (thus all subdomains). Exclusion list is given as a file with `-e` argument, if no such list is given, known malicious domains are excluded by default. At the moment known malicious domains are (ref: [CVE-2022-46405](https://www.cve.org/CVERecord?id=CVE-2022-46405): 
- *.activitypub-troll.cf
- *.misskey-forkbomb.cf
- *.repl.co

Finally, if needed, verbose logging can be enabled with `-v` argument. This should not be needed for normal uses, it is mostly for debugging.

The execution of `masnet.download` can be terminated gracefully with `Ctrl-C`. Graceful exit means that running threads will be given time to terminate, so it will take some seconds. If you want to terminate immediately, you can use `Ctrl-C` once or a few times more. If terminated immediately, the peers data of some domains visited may not be saved.

All expected errors are handled gracefully with no stack trace printed to stdout or stderr. If you see any stack trace, that means there is an unexpected error and then the outputs of the program cannot be trusted.

At the end of an execution (also when terminated by Ctrl-C), in addition to (many) `peers.json.gz` and `.error` files, 3 files are generated containing:

- list of (successfully) visited domains given by `--output-visits` argument, default file is `visits.out`.
- list of domains where an error encountered given by `--output-errors` argument, default file is `errors.out`.
- list of skipped domains because of exclusion given by `--output-skips` argument, default file is `skips.out`.

errors and skips files are only for information, whereas visits and peers.json.gz files will be used with `masnet.generate` to further process the network.

Because there is going to be many peers.jzon.gz files, the output directory can be specified with `-o` argument. By default it uses the current directory. The visits, errors and skips files are also saved under the directory specified. If the directory specified does not exist, it is created.

Just for demonstration, `masnet.download` can be run only for a minute using `--demo` argument. It takes longer than a minute because already running tasks will be waited until they finish but no new task will be scheduled after a minute. This is enough for visiting some domains and gathering some data for a simple demonstration.

An example run, discarding all existing files, 100 threads, 15s timeout, saving files to tmp folder and running in demo mode (60 seconds) would be:

```
$ masnet.download --demo -d -n 100 -t 15 -o tmp
```

This command will print (to stdout) a status line like:

```
d:006576 e:009424 s:01508073 qd:00033131 e:00:19:12 da:1.20
```

The meaning of the fields are:

- d: # of domains visited with success (peers data is downloaded and being used)
- e: # of domains visited with error (peers data cannot be downloaded)
- s: # of skipped domains (due to exclusion)
- qd: # of domains in download queue (to be visited)
- e: elapsed time hh:mm:ss
- da: average download time in seconds

The status line is printed every second and at the end of the execution.

# Release History

0.2:
- major rewrite of masnet.download
- initial release of masnet.generate

0.1.1:
- small fixes
    
0.1:
- initial release of masnet.download
