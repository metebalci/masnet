
# masnet

`masnet` includes basic tools for Mastodon network/graph analysis.

`masnet.download` downloads the required data from Mastodon instances to create Mastodon network.

# masnet.download

`masnet.download` connects to a given start domain (given with `-s` argument), downloads its peers (api/v1/instance/peers), and then repeats this for each peer until all domains are visited. 

After downloading the peers data of a domain, it is saved to a gzipped file (filename is domain name where `\` is replaced with `_` with `.peers.json.gz` suffix). Thus, it is possible to restart the download safely. If needed, saved files can be discarded (with `-d`) and all of them are downloaded again.

For network connections, a timeout can be specified with `-t` argument.

Because the download process is very I/O oriented, a number of Python threads are created to concurrently fetch peers of different domains. The number of these threads can be specified with `-n` argument. As each thread opens at least one file, large number of threads may require you to increase the system limit for the maximum files that can be opened.

Because there can be (many) malicious domains, it is possible to exclude them from traversal as they are seen in peers. Exclusion is specified as a string matching the domain name from the end, hence it is possible to filter all subdomains with a single string. For example, `.activitypub-troll.cf` would filter any domain ending with this (thus all subdomains). Exclusion list is given as a file with `-e` argument, if no such list is given, known malicious domains are excluded by default. At the moment known malicious domains are (ref: [CVE-2022-46405](https://www.cve.org/CVERecord?id=CVE-2022-46405): 
- *.activitypub-troll.cf
- *.misskey-forkbomb.cf
- *.repl.co

Finally, if needed, verbose logging can be enabled with `-v` argument. This should not be needed for normal uses, it is mostly for debugging.

The execution of `masnet.download` can be terminated gracefully with `Ctrl-C`. Graceful exit means that already running tasks will be waited until they finish, so graceful exit takes some time. If you want to terminate immediately, you can use `Ctrl-C` once or a few times more. If terminated immediately, the peers data of some domains visited may not be saved.

All expected errors are handled gracefully with no stack trace printed to stdout or stderr. If you see any stack trace, that means there is an unexpected error and then the outputs of the program cannot be trusted.

At the end of execution (also when terminated by Ctrl-C), in addition to (many) `peers.json.gz` files, 3 files are generated containing:

- list of visited domains given by `--output-visits` argument, default file is `visits.out`.
- list of encountered errors given by `--output-errors` argument, default file is `errors.out`.
- list of skipped domains because of exclusion given by `--output-skips` argument, default file is `skips.out`.

errors and skips files are only for information, whereas visits and peers.json.gz files will be used with `masnet.generate` to further process the network.

Because there is going to be many peers.jzon.gz files, the output directory can be specified with `-o` argument. By default it uses the current directory. The visits, errors and skips files are also saved under the directory specified.

Just for demonstration, `masnet.download` can be run only for a minute using `--demo` argument. It takes longer than a minute because already running tasks will be waited until they finish but no new task will be scheduled after a minute. This is enough for visiting some domains and gathering some data for a simple demonstration.

An example run, discarding all existing files, 100 threads, 15s timeout, saving files to tmp folder and running in demo mode (60 seconds) would be:

```
$ masnet.download --demo -d -n 100 -t 15 -o tmp 2> error
```

It is a good practice to redirect stderr to a file, and use `tail -f` to monitor errors because there will be many domains not responding. This command will print (to stdout) a status line like:

```
vp:048081 vd:000193 e:000143 d:000000 s:00007343 p:0.4% t:0000:20
```

The meaning of the fields are:

- vp: visits pending (=visits done + visits scheduled)
- vd: visits done (peers saved, includes errors)
- e: errors (error happened during a visit)
- d: domains (visits to be scheduled, stays at 0 when all are scheduled)
- s: skips (domains skipped due to exclusion)
- p: percent completed (this can naturally change as more peers are discovered particularly at the beginning of network discovery also depending on the start domain, but it gets more stable as more domains are visited)
- t: elapsed time in minutes:seconds

The status line is printed every 5 seconds and at the end of the execution. At the moment all numbers (but s) are printed with zero prefixed 6 digits (s with 8 digits), which is enough for current Mastodon network.

# Release History

0.1.1:
- small fixes
    
0.1:
- initial release of masnet.download
