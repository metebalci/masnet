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
from masnet import write_graph

# pylint: disable=too-many-statements
# pylint: disable=too-many-locals
def main():
    print('masnet v%s' % get_version())
    parser = argparse.ArgumentParser(prog='masnet.generate',
                                     description='',
                                     epilog='')

    parser.add_argument('-d', '--dir',
                        help='use specified directory for files ' \
                             '(default: current directory)',
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

    nodes = {}
    edges = []
    start = time.time()

    def print_status():
        elapsed = time.time() - start
        hours = int(elapsed / 3600)
        minutes = int((elapsed - hours * 3600) / 60)
        seconds = elapsed - minutes * 60 - hours * 3600
        print('n:%08d e:%08d ' \
              't:%02d:%02d:%02d ' % (len(nodes), len(edges),
                                     hours, minutes, seconds))


    try:
        # load domains from peers.json files
        # this is the best way because otherwise exclusion and errors has to
        # be re-checked, computationally expensive
        # we already know these passed exclusion and has peers info
        print('creating nodes...')
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
                peers = doc['peers']
                nodes[domain] = {'id': len(nodes),
                                 'peers': peers}
        # create edges
        # also filter non-existent peers
        print('creating edges...')
        last_status = time.time() - 10
        for doc in nodes.values():
            if (time.time() - last_status) > 1:
                print_status()
                last_status = time.time()
            domain_id = doc['id']
            for peer_name in doc['peers']:
                # there should be no need for None and len=0 checks
                # but I saw such data can be returned from peers api call
                # so clean it up
                if peer_name is None:
                    continue
                if len(peer_name.strip()) == 0:
                    continue
                # filter if not exist in nodes
                if peer_name in nodes:
                    peer_id = nodes[peer_name]['id']
                    edges.append((domain_id, peer_id))

        print_status()

        write_graph(nodes, edges)
        print('saved to masnet.generate.graph')

    except KeyboardInterrupt:
        pass

    print('bye.')

if __name__ == '__main__':
    main()
