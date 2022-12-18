# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement
# pylint: disable=bare-except,broad-except
import argparse
import glob
import json
import time
from masnet import get_version, set_verbose, set_debug, set_working_dir
from masnet import debug, get_path
from masnet import save_graph, percent_progress
from masnet import save_labels, load_labels

# pylint: disable=too-many-statements
# pylint: disable=too-many-locals
def main():
    print('masnet v%s' % get_version())
    parser = argparse.ArgumentParser(prog='masnet.generate',
                                     description='',
                                     epilog='')

    parser.add_argument('-d', '--dir',
                        help='use specified directory for files',
                        required=False)

    parser.add_argument('--debug',
                        help='enables debug logging',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('-v', '--verbose',
                        help='enable verbose logging, mostly for development',
                        action='store_true',
                        required=False,
                        default=False)

    args = parser.parse_args()
    set_debug(args.debug)
    set_verbose(args.verbose)
    debug(str(args))
    set_working_dir(args.dir)

    # node_id -> label (domain)
    id2label = {}
    # label -> node_id
    label2id = {}
    # node_id -> adjlist of this node
    adjlist = {}
    # node_id -> list of peers from json (domain names)
    peers = {}
    num_nodes = 0
    num_links = 0
    start = time.time()

    def print_status():
        elapsed = time.time() - start
        hours = int(elapsed / 3600)
        minutes = int((elapsed - hours * 3600) / 60)
        seconds = elapsed - minutes * 60 - hours * 3600
        print('N:%08d L:%08d ' \
              'e:%02d:%02d:%02d ' % (num_nodes, num_links,
                                     hours, minutes, seconds), flush=True)


    try:
        # load domains from peers.json files
        # this is the best way because otherwise exclusion and errors has to
        # be re-checked, computationally expensive
        # we already know these passed exclusion and has peers info
        print('creating the graph from peers...')
        last_status = time.time() - 10
        for file_name in glob.glob(get_path('*.peers.json')):
            if (time.time() - last_status) > 1:
                print_status()
                last_status = time.time()
            with open(file_name, 'r') as f:
                doc = json.load(f)
                # reading the domain from the file, so this is the actual
                # domain
                domain = doc['domain']
                node_id = num_nodes
                num_nodes = num_nodes + 1
                label2id[domain] = node_id
                id2label[node_id] = domain
                peers[node_id] = doc['peers']
                # adjlist is a set, hence no multiple links
                adjlist[node_id] = set()
        for node_id, node_peers in peers.items():
            if (time.time() - last_status) > 1:
                print_status()
                last_status = time.time()
            for peer_name in node_peers:
                # there should be no need for None and len=0 checks
                # but I saw such data can be returned from peers api call
                # so clean it up
                if peer_name is None:
                    continue
                if len(peer_name.strip()) == 0:
                    continue
                # filter if peer is not a known node
                # Mastodon peers usually contain many strange domains:
                # - private IP addresses
                # - malicious domains
                # - not working domains
                if peer_name in label2id:
                    peer_node_id = label2id[peer_name]
                    # do not allow self-loops
                    if peer_node_id != node_id:
                        adjlist[node_id].add(peer_node_id)
                        num_links = num_links + 1

        del peers

        print_status()
        print('graph created.')

        save_labels(id2label,
                    get_path('mastodon.labels'))
        print('labels saved.')

        del id2label
        del label2id

        print('saving graphs...')
        save_graph(adjlist,
                   False,
                   get_path('mastodon.networkit.undirected'),
                   progressfn=percent_progress)
        save_graph(adjlist,
                   True,
                   get_path('mastodon.networkit.directed'),
                   progressfn=percent_progress)
        print('graphs saved.')

    except KeyboardInterrupt:
        pass

    print('bye.')

if __name__ == '__main__':
    main()
