
# masnet

`masnet` includes basic tools for Mastodon network/graph analysis. 

It can be installed by executing `pip install masnet`. 

After installation, following commands can be used: 

- `masnet.download`: downloads peers information from Mastodon instances.

- `masnet.generate`: creates Mastodon graph using the peers information downloaded.

- `masnet.analyze`: performs basic graph/network analysis on Mastodon graph.

There a few common arguments to each command:

- `-d <directory>`: uses the directory instead of the current directory to read and/or write files to. If the directory specified does not exist, it is created. This is important as `masnet.download` creates a lot of files and `masnet.generate` reads them.

- `-v`: enables verbose logging. It should not be normally needed.

- `--debug`: enables debug logging. It is only to be used during development.

Each command provide verbose logging with `-v` argument and debug logging with `--debug` argument.

# hardware requirements

Mastodon graph has over 10K vertices and more than 20M edges.

# masnet.download

`masnet.download` connects to a given start domain (given with `-s` argument), downloads its peers (with `api/v1/instance/peers` API call), and then repeats this for each peer until all domains are visited. If start domain is not specified, `mastodon.social` is used.

After downloading the peers information of a domain, it is saved to `<domain>.peers.json` (any `/` in domain is replaced with `_` for the filename). Thus, it is possible to restart the download after a graceful exit. If needed, saved files can be discarded (with `--discard` argument) and all of them are downloaded again (existing files are not deleted but when needed overwritten).

In addition to caching the API response, `masnet.download` also saves the http or network errors to `<domain>.error` files in order to not try to connect these after a restart. This behaviour is not controlled with `-d` argument, it is always enabled. If you want to retry these domains, you can delete the error files.

For network connections, a timeout in seconds can be specified with `-t` argument. System default timeout is usually too high, I recommend experimenting with lower values such as 15 (seconds).

Because the download process is network I/O heavy, a number of Python threads are created to concurrently fetch peers data of different domains. The number of these threads can be specified with `-n` argument. If not specified, four times the cpu count threads for download are created. In addition to download threads, four more threads are created in addition to the program main thread. Each of these threads are working independently, fetching the request from its own queue and either creating a response in another queue (which is an input for another thread) or terminates the processing there (e.g. by writing the result to a file). Inter-thread communication is done using Python's `deque` because it provides bi-directional, non-blocking and thread-safe O(1) `append` and `pop` methods. I

Because there are (many) malicious or irrelevant domains in Mastodon network, it is possible to exclude them from traversal as they are seen in peers. Exclusion is specified as regular expression patterns. The name of the file containing such patterns can given with `-e` argument. If not specified, a default list (`masnet/default_exclusion_patterns`) is used. This default list excludes all private IP spaces, special domain names and known malicious domains at the time of release.

`masnet.download` is a long running process, approx. 60 minutes on my computer. The execution of `masnet.download` can be terminated gracefully with `Ctrl-C`. Graceful exit means that running threads will be given time to terminate properly, so it will take some seconds. If you want to terminate immediately, you can use `Ctrl-C` once or a few times more. If terminated immediately, the peers information of some domains may not be saved, so if you care about data consistency or plan to restart the run, terminate the execution gracefully.

All expected errors are handled gracefully with no stack trace printed to stdout or stderr. If you see any stack trace, that means there is an unexpected error and then the outputs of the program cannot be trusted.

At the end of an execution (also when terminated by Ctrl-C), in addition to (many) `peers.json` and `.error` files, 5 files are generated:

- `masnet.download.visits`: list of (successfully) visited domains
- `masnet.download.errors`: list of domains where an error is encountered. For each domain, after a space, also the error message is saved.
- `masnet.download.skips`: list of skipped domains due exclusion patterns
- `masnet.download.times`: list of download times (in ms) of each peers.json file
- `masnet.download.log`: a few information that might be useful to remember the context of this execution

All files other than `*.peers.json` are only for information. Only `*.peers.json` files are used by `masnet.generate`.

An example run, with 30s timeout, saving files to current directory would be:

```
$ masnet.download -t 30
```

This command will print (to stdout) a status line like:

```
d:011740 e:032335 s:02008264 qd:00007320 t:00:46:22 da:193 to:58
```

The meaning of the fields are:

- d: # of domains visited with success (peers data is downloaded and being used)
- e: # of domains visited with error (peers data cannot be downloaded)
- s: # of skipped domains (due to exclusion)
- qd: # of domains in download queue (to be visited)
- t: elapsed time hh:mm:ss
- da: average download time in seconds
- to: number of connections gave timeout error

The status line is printed every second and at the end of the execution.

`masnet.download` finishes automatically when there are zero elements observed in download queue (qd=0 above) for 5 seconds. This is not a 100% correct termination condition as by chance there can be download threads waiting at the same time while download queue is empty but this is almost impossible to occur.

If you observe too many timed out connections (`to` above), you should use a longer time out value. With `-t 30`, I see around 100 time outs.

As of 2022-12-12, it takes more than an hour for `masnet.download` to complete a full traversal of Mastodon network on a 4-core virtual machine with 30 seconds timeout, with the status line below:

```
d:011816 e:039811 s:02113992 qd:00000000 t:01:28:10 da:485 to:77
```

# masnet.generate

`masnet.generate` reads the .peers.json files saved by `masnet.download` and creates a graph and saves it in networkit Binary format to `mastodon.graph` file. This step is to optimize graph reading time for the analysis. In addition to the graph, the actual labels (domains) are also save into `mastodon.labels` file. Both of these files are read by `masnet.analyze`.

Each `peers.json` file (thus a working domain) will be represented by a vertex in the graph, and it will have connections to its peers as long as the peer also has `peers.json` file. This is the quickest and cleanest approach to create the graph.

```
$ masnet.generate
masnet v0.2
creating the graph from peers...
v:00000000 e:00000000 t:00:00:00 
v:00000562 e:00000000 t:00:00:01 
... repeats lines like this ...
:00011775 e:23631551 t:00:00:38 
graph created.
labels saved.
saving graph...
0% 31% 59% 80% 99% WARNING:root:overriding given file
100%
graph saved.
bye.
```

where `v` means number of vertices, `e` means number of edges and `t` means elapsed time.

This is a relatively fast operation, it completes under a minute.

# masnet.analyze

`masnet.analyze` performs basic graph/network analysis on Mastodon graph using `networkit` large-scale network analysis toolkit. As its core is written in C++ using OpenMP, it is close to being as fast as possible.

Each analysis is requested with an argument to `masnet.analyze` and multiple analysis can be performed at the same run (they run sequentially). Please check the help with `--help` to see a list of analysis.

For example, the run below calculates and writes in and out degrees to a file (`mastodon.degrees`) and displays the top 10 nodes with the most degree centrality.

```
$ masnet.analyze --degree-distribution --degree-centrality-ranks
masnet v0.2
vertex labels loaded.
reading graph into networkit...
graph read in 1.6 seconds.
calculating degrees...
saving degrees...
done.
tealnetwork.org 0.973
friends.joinfediverse.online 0.972
hallole.eu 0.972
goatdaddy.net 0.970
dis-le.de 0.967
fr.droidbuilders.uk 0.967
friendica.drk.network 0.965
soc.villisek.fr 0.964
twotingwafu.rikozone.net 0.963
amical.info 0.963
bye.
```
# Release History

0.2:
- major rewrite of masnet.download
- initial release of masnet.generate
- initial release of masnet.analyze

0.1.1:
- small fixes
    
0.1:
- initial release of masnet.download
