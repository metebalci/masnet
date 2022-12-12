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

    # vertex_id -> label (domain)
    id2label = {}
    # label -> vertex_id
    label2id = {}
    # vertex_id -> adjlist of this vertex
    adjlist = {}
    # vertex_id -> list of peers from json (domain names)
    peers = {}
    num_vertices = 0
    num_edges = 0
    start = time.time()

    def print_status():
        elapsed = time.time() - start
        hours = int(elapsed / 3600)
        minutes = int((elapsed - hours * 3600) / 60)
        seconds = elapsed - minutes * 60 - hours * 3600
        print('v:%08d e:%08d ' \
              't:%02d:%02d:%02d ' % (num_vertices, num_edges,
                                     hours, minutes, seconds))


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
                vertex_id = num_vertices
                num_vertices = num_vertices + 1
                label2id[domain] = vertex_id
                id2label[vertex_id] = domain
                peers[vertex_id] = doc['peers']
                # adjlist is a set, hence no multiple edges
                adjlist[vertex_id] = set()
        for vertex_id, vertex_peers in peers.items():
            if (time.time() - last_status) > 1:
                print_status()
                last_status = time.time()
            for peer_name in vertex_peers:
                # there should be no need for None and len=0 checks
                # but I saw such data can be returned from peers api call
                # so clean it up
                if peer_name is None:
                    continue
                if len(peer_name.strip()) == 0:
                    continue
                # filter if peer is not a known vertex
                # Mastodon peers usually contain many strange domains:
                # - private IP addresses
                # - malicious domains
                # - not working domains
                if peer_name in label2id:
                    peer_vertex_id = label2id[peer_name]
                    # do not allow self-loops
                    if peer_vertex_id != vertex_id:
                        adjlist[vertex_id].add(peer_vertex_id)
                        num_edges = num_edges + 1

        del peers

        print_status()
        print('graph created.')

        save_labels(id2label,
                    get_path('mastodon.labels'))
        print('labels saved.')

        del id2label
        del label2id

        print('saving graph...')
        save_graph(adjlist,
                   get_path('mastodon.graph'),
                   progressfn=percent_progress)
        print('graph saved.')

    except KeyboardInterrupt:
        pass

    print('bye.')

if __name__ == '__main__':
    main()
