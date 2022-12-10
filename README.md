
# masnet

`masnet` includes basic tools for Mastodon network/graph analysis.

`masnet.download` downloads peers information from Mastodon instances.

`masnet.generate` creates Mastodon graph representation using the peers information downloaded.

`masnet.analyze` performs basic graph/network analysis on Mastodon graph.

# masnet.download

`masnet.download` connects to a given start domain (given with `-s` argument), downloads its peers (api/v1/instance/peers), and then repeats this for each peer until all domains are visited. 

After downloading the peers data of a domain, it is saved to `<domain>.peers.json`. Thus, it is possible to restart the download safely. If needed, saved files can be discarded (with `-d`) and all of them are downloaded again (existing files are not deleted but when needed overwritten). `/` characters in domain is also replaced with `_` for the file name.

In addition to caching the API response, `masnet.download` also saves the http or network errors to `<domain>.error` files in order to not try to connect these after a restart. This behaviour is not controlled with `-d` argument, it is always enabled. If you want to retry these domains, delete the error files.

For network connections, a timeout in seconds can be specified with `-t` argument. System default timeout is usually too high, I recommend experimenting with lower values such as 15 (seconds).

Because the download process is I/O heavy, a number of Python threads are created to concurrently fetch peers data of different domains. The number of these threads can be specified with `-n` argument. By default, four times the cpu count download threads are created. Inter-thread communication is done using Python's `deque` because it provides bi-directional, non-blocking and thread-safe O(1) `append` and `pop` methods.

Because there can be (many) malicious (or irrelevant) domains, it is possible to exclude them from traversal as they are seen in peers. Exclusion is specified as a string matching the domain name from the end, hence it is possible to filter all subdomains with a single string. For example, `.activitypub-troll.cf` would filter any domain ending with this (thus all subdomains). Exclusion list is given as a file with `-e` argument, if no such list is given, known malicious domains are excluded by default. You can see them in `masnet/__init__.py` code.

Finally, if needed, verbose logging can be enabled with `-v` argument. This should not be needed for normal uses, it is mostly for debugging.

The execution of `masnet.download` can be terminated gracefully with `Ctrl-C`. Graceful exit means that running threads will be given time to terminate, so it will take some seconds. If you want to terminate immediately, you can use `Ctrl-C` once or a few times more. If terminated immediately, the peers data of some domains may not be saved, so if you care about data consistency or plan to restart the run, it is highly recommended to wait for threads to terminate on their own.

All expected errors are handled gracefully with no stack trace printed to stdout or stderr. If you see any stack trace, that means there is an unexpected error and then the outputs of the program cannot be trusted.

At the end of an execution (also when terminated by Ctrl-C), in addition to (many) `peers.json` and `.error` files, 5 files are generated:

- `masnet.download.visits`: list of (successfully) visited domains
- `masnet.download.errors`: list of domains where an error is encountered. For each domain, after a space, also the error message is saved.
- `masnet.download.skips`: list of skipped domains
- `masnet.download.times`: list of download times (in ms) of each peers.json file
- `masnet.download.log`: a few information that might be useful to remember the context of this execution

All files other than `*.peers.json` are only for information. Only peers.json files are used by `masnet.generate`.

Because there is going to be many peers.jzon files, the output directory can be specified with `-o` argument. By default it uses the current directory. All other files are also created in this directory. If the directory specified does not exist, it is created.

An example run, with 30s timeout, saving files to current directory would be:

```
$ masnet.download -t 30
```

This command will print (to stdout) a status line like:

```
d:011740 e:032335 s:02008264 qd:00007320 e:00:46:22 da:193 to:58
```

The meaning of the fields are:

- d: # of domains visited with success (peers data is downloaded and being used)
- e: # of domains visited with error (peers data cannot be downloaded)
- s: # of skipped domains (due to exclusion)
- qd: # of domains in download queue (to be visited)
- e: elapsed time hh:mm:ss
- da: average download time in seconds
- to: number of connections gave timeout error

The status line is printed every second and at the end of the execution.

As of writing this (2022-12-09), it takes around 60 minutes for masnet.download to finish on a 4-core virtual machine.

# masnet.generate

`masnet.generate` reads the .peers.json files saved by `masnet.download` and creates a graph representation and saves it to `masnet.generate.graph` file. This step is to optimize graph representation for the analysis.

`masnet.generate.graph` will be a large file like 200MB.

```
$ masnet.generate
```

displays an output like this:

```
masnet v0.2
creating nodes...
n:00000000 e:00000000 t:00:00:00 
n:00003082 e:00000000 t:00:00:01 
... multiple such lines ...
creating edges...
n:00011775 e:00000000 t:00:00:04 
n:00011775 e:00739210 t:00:00:05 
... multiple such lines ...
saved to masnet.generate.graph
bye.
```

where `n` means number of nodes, `e` means number of edges and `t` means elapsed time.

As of writing this (2022-12-10), it takes less than a minute to generate the graph.

## masnet.generate.graph format

It is saved using Python struct pack/unpack methods. The field types below corresponds to the ones used in pack/unpack methods. All fields are saved in network byte order (with `!` in struct).

```
I: number of nodes (N)
for node 0 to N
  I: node id
  I: length of string below
  bytes[]: domain in utf-8 encoding representation saved with .encode('utf-8')
I: number of edges (E)
for edge 0 to E
  I: source node id
  I: destination node id
```

# masnet.analyze

*masnet.generate.graph.gz can also be analyzed directly with your tools. See the format description above.*

`masnet.analyze` performs basic graph/network analysis on Mastodon graph saved by `masnet.generate`.

# Release History

0.2:
- major rewrite of masnet.download
- initial release of masnet.generate
- initial release of masnet.analyze

0.1.1:
- small fixes
    
0.1:
- initial release of masnet.download
