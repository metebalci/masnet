
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

In the software and documentation, I prefer to use the term Graph (rather than Network) but instead of Vertex and Edge, I try to stick to terms Node and Link.

The input and output file names cannot be customized, as I think the tools will be run on a clean directory (due to large number of files).

# Hardware Requirements

Mastodon graph has over 10K nodes and more than 20M links. It is not a large graph, but also not small. 

The tools in `masnet` have different requirements:

- `masnet.download` is network I/O intensive. It is implemented as an async single-thread app using Python's `asyncio` and async libraries `aiohttp`, `aiodns` and `aiofile`.

- `masnet.generate` is memory intensive. It consumes more than 4GB of memory at its peak. I recommend having more than 4GB of free memory, hence a computer with 8GB of memory should be OK.

- `masnet.analyze` is compute intensive and uses less memory than `masnet.generate`. As the algorithms are optimized with OpenMP in `networkit` package, the more cores you have the faster it will run.

I am running the tools on an Ubuntu Linux virtual machine with 8 cores and 16GB of memory.

# masnet.download

```
Input Files: none

Output Files:
    - <domain>.peers.json files
    - masnet.download.visits
    - masnet.download.errors
    - masnet.download.skips
    - masnet.download.times
```

`masnet.download` connects to a given start domain (given with `-s` argument), downloads its peers (with `api/v1/instance/peers` API call), and then repeats this for each peer until all domains are visited. If start domain is not specified, `mastodon.social` is used.

After downloading the peers information of a domain, it is saved to `<domain>.peers.json`. `peers.json` file is not the same as `instance/peers` API response, it is augmented with the domain name, thus contains a `domain` key with the value of domain name, and a `peers` key with the list of domain names of peers.

For network connections, a timeout in seconds can be specified with `-t` argument. System default timeout is usually too high, I recommend experimenting with lower values such as 30 (seconds).

Because the download process is mostly network I/O, a number of tasks are needed to fetch peers data of different domains. These tasks are implemented as coroutines in Python. The number of tasks can be specified with `-n` argument (default is 100). 

Because there are (many) malicious or irrelevant domains in Mastodon network, it is possible to exclude them from traversal as they are seen in peers. Exclusion is specified as regular expression patterns. The name of the file containing such patterns can given with `-e` argument. If not specified, a default list (`masnet/default_exclusion_patterns`) is used. This default list excludes all private IP spaces, special domain names and known malicious domains at the time of release. It also filters URLs (names containing `/`).

`masnet.download` is a long running process. The execution of `masnet.download` can be terminated with `Ctrl-C`. Since it is a long running process, it might be a good idea to pipe the output to `tee` and save the output to a log file. 

All expected errors are handled gracefully with no stack trace printed to stdout or stderr. If you see any stack trace, that means there is an unexpected error and you can report it as an issue on GitHub.

At the end of an execution (also when terminated by Ctrl-C), in addition to (many) `<domain>.peers.json` filoes, 4 more files are generated:

- `masnet.download.visits`: list of (successfully) visited domains
- `masnet.download.errors`: list of domains where an error is encountered. For each domain, after a space, also the error message is saved.
- `masnet.download.skips`: list of skipped domains due exclusion patterns
- `masnet.download.times`: list of download times (in ms) of each peers.json file

All files other than `<domain>.peers.json` files are only for information. Only `<domain>.peers.json` files are used by `masnet.generate`.

An example run, with 30s timeout, saving files to current directory would be:

```
$ masnet.download -t 30
```

This command will print (to stdout) a status line like:

```
q:000000 a:000001 s:138374 N:011867 L:039653324 e:00126507 s:01990292 to:14706 t:00:39:41
```

The meaning of the fields are:

- q: # of domains in queue (of which peers information will be fetched)
- a: # of async tasks
- s: # of scheduled domains (already downloaded and will be downloaded)

- N: # of domains of which peers information is fetched successfully
- L: # of links observed

- e: # of domains where an error happened during fetch
- s: # of skipped domains (due to exclusion)
- to: number of connections gave timeout error

- t: elapsed time hh:mm:ss

The status line is printed every second and at the end of the execution.

The links observed reported with `L` is higher than what `masnet.generate` will report. This is because `masnet.download` counts links also for probably error returning domains. The number of nodes `N` and number of links observed `L` are only for information, accurate number of nodes and links will be reported by `masnet.generate`.

You might see increasing (much more than N) error e and skipped s numbers. At least at the moment, there are many domains in Mastodon network that are either malicious (there are many randomly named subdomains of some domains) or invalid like a private IP. Hence, there are much more domains in peers than the ones actually working.

`masnet.download` terminates automatically when there are zero elements observed in queue and there is only one task (which is the main program, that means no download tasks) for 5 seconds.

On 2022-12-18, `masnet.download -t 30 -n 100` and `masnet.download -t 30 -n 1000` both completes around 75 minutes with the following outputs:

```
$ masnet.download -t 30 -n 100
....
q:000000 a:000001 s:139500 N:013678 L:047071155 e:00125822 s:02981916 to:4241 t:01:15:26
```

```
$ masnet.download -t 30 -n 1000
...
q:000000 a:000001 s:139483 N:013688 L:047105958 e:00125795 s:02990283 to:3956 t:01:13:15
```

If you enable verbose mode with `-v` argument, after the status line, top 5 parent domains encountered during graph traversal will be displayed like below (parent meaning the top domain name part is removed, for a.b.com, it is b.com). This would help to identify malicious or invalid domains.

# masnet.generate

```
Input Files: <domain>.peers.json files

Output Files: 
    - mastodon.networkit 
    - mastodon.labels
```

`masnet.generate` reads all `<domain>.peers.json` files saved by `masnet.download` and creates a graph and saves it in networkit Binary format to `mastodon.networkit.directed` and `mastodon.networkit.undirected` files. The Mastodon peers network is normally directed, but undirected version is also saved by ignoring the direction of peer relationship. In addition to the graphs, the actual labels (domains) are also save into `mastodon.labels` file. Both of these files are read by `masnet.analyze`. Both directed and undirected networks have same nodes and node ids.

Each `<domain>.peers.json` file (thus a working domain) will be represented by a node in the graph, and it will have connections to its peers as long as the peer also has its `<domain>.peers.json` file. Thus if a domain returns error (for the API call) or skipped/exluded, it is also skipped in the generated network, no such node will exist.

```
$ masnet.generate
masnet v0.2
creating the graph from peers...
N:00000000 L:00000000 e:00:00:00 
N:00000562 L:00000000 e:00:00:01 
... repeats lines like this ...
:00011775 e:23631551 t:00:00:38 
graph created.
labels saved.
saving graphs...
0% 46% 76% 99% 100%
0% 26% 49% 70% 91% 100%
graphs saved.
bye.
```

where `N` means number of nodes, `L` means number of links and `e` means elapsed time.

This is a relatively fast operation, it completes under a minute.

# masnet.analyze

```
Input Files: 
    - mastodon.networkit.directed or mastodon.network.undirected
    - mastodon.labels

Output Files: depends on the analysis
```

`masnet.analyze` performs basic graph/network analysis on Mastodon graph using `networkit` large-scale network analysis toolkit. As the core of `networkit` is written in C++ using OpenMP, it is quite a fast implementation.

The input graph file is selected using `--directed` argument. By default, the undirected graph is used (mastodon.networkit.undirected).

Running `masnet.analyze` with `--card` argument shows the [network card](https://doi.org/10.1007/s41109-022-00514-7) of Mastodon network specified in `mastodon.networkit`.

```
$ masnet.analyze --card
masnet v0.3
node labels loaded.
reading undirected graph into networkit...
graph read in 0.6 seconds.
generating the network card...
----------------------------  --------------------------------
Name                          Mastodon peers network
Kind                          undirected, unweighted
Nodes are                     Mastodon instances
Links are                     Peer relationship
----------------------------  --------------------------------
Number of nodes               13688
Number of links               16010592
Degree*                       2339.362 [0, 12881]
Clustering                    0.754
Connected                     2 components [100.0% in largest]
Component size*               6844.0 [1, 13687]
Diameter                      n/a
Largest component's diameter  4
----------------------------  --------------------------------
Data generating process       masnet.download, masnet.generate
----------------------------  --------------------------------
*: avg [min, max]
```

Each analysis is requested with an argument to `masnet.analyze`. Please check the help with `--help` to see a list. At the moment, the following analysis arguments are supported (there are others mark experimental which I am developing/testing):

- `--card`: shows the network card

# Release History

0.3.1:
- pypi fix

0.3:
- major rewrite of masnet.download
- some changes on masnet.generate and masnet.analyze

0.2.1:
- terms fixed to Node and Link (rather than Vertex and Edge)
- masnet.analyze improvements
- masnet.downloads fix for termination of download threads

0.2:
- major rewrite of masnet.download
- initial release of masnet.generate
- initial release of masnet.analyze

0.1.1:
- small fixes
    
0.1:
- initial release of masnet.download
