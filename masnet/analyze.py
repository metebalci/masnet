# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement
# pylint: disable=bare-except,broad-except
import argparse
import networkx
import time
from masnet import get_version, set_verbose, set_debug, set_working_dir
from masnet import debug, get_path
from masnet import read_graph

# pylint: disable=too-many-statements
# pylint: disable=too-many-locals
def main():
    print('masnet v%s' % get_version())
    parser = argparse.ArgumentParser(prog='masnet.generate',
                                     description='',
                                     epilog='')

    parser.add_argument('--debug',
                        help='enables debug logging',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('-g', '--graph',
                        help='use specified graph file ' \
                             '(default: masnet.generate.graph)',
                        required=False,
                        default='masnet.generate.graph')

    parser.add_argument('-v', '--verbose',
                        help='enable verbose logging, mostly for development',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('--degree-centrality',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('--greedy-modularity',
                        action='store_true',
                        required=False,
                        default=False)

    args = parser.parse_args()
    set_debug(args.debug)
    set_verbose(args.verbose)
    debug(str(args))
    set_working_dir(None)

    nodes, edges = read_graph(args.graph)
    g = networkx.DiGraph(edges)
    # save memory, edges consume~3GB
    del edges

    if args.degree_centrality:

        res = networkx.algorithms.degree_centrality(g)
        sorted_nodes = sorted(res.keys(), key=lambda x: res[x])
        for i in range(0, 5):
            key = sorted_nodes[i]
            print("%d: %d" % (key, res[key]))

    elif args.greedy_modularity:

        communs = networkx.algorithms.community.greedy_modularity_communities(g)
        for commun in communs:
            print(len(commun))

    print('bye.')

if __name__ == '__main__':
    main()
